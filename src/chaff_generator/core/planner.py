"""Planner: turns a target volume into a sequence of planned files.

The planner owns every random decision that is *not* file content — format
choice, size draw, directory, filename — driven by its own seeded RNG so the
same master seed always produces the same file plan on every OS (spec
sections 11, 25-26).
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from chaff_generator.content import generators as gen
from chaff_generator.core.models import LayoutMode
from chaff_generator.core.paths import PathAllocator, sanitize_filename
from chaff_generator.core.seeding import derive_file_seed
from chaff_generator.profiles.models import DEFAULT_AVG_SIZES, DEFAULT_SIZE_RANGES, SizeRange

if TYPE_CHECKING:
    from chaff_generator.content.bank import ChaffBank
    from chaff_generator.content.world import GenerationWorld
    from chaff_generator.core.models import GenerationConfig
    from chaff_generator.profiles.models import Profile
    from chaff_generator.renderers.base import RendererCapabilities
    from chaff_generator.templates.models import TemplateDef, TemplateRegistry

#: Final extension per renderer id; "dev" picks from a menu instead.
EXTENSIONS: dict[str, str] = {
    "txt": "txt",
    "log": "log",
    "md": "md",
    "html": "html",
    "csv": "csv",
    "json": "json",
    "xml": "xml",
    "eml": "eml",
    "docx": "docx",
    "pdf": "pdf",
    "xlsx": "xlsx",
    "pptx": "pptx",
    "vcf": "vcf",
    "ics": "ics",
    "dat": "dat",
}

#: Extensions the developer-artifact renderer cycles through.
DEV_EXTENSIONS: tuple[str, ...] = ("py", "py", "sql", "yaml", "yml", "toml", "md", "")

#: Template kinds that can feed each renderer, in preference order.
TEMPLATE_KINDS: dict[str, tuple[str, ...]] = {
    "txt": ("prose",),
    "md": ("prose",),
    "html": ("prose",),
    "docx": ("prose",),
    "pdf": ("prose",),
    "eml": ("email",),
    "csv": ("tabular",),
    "xlsx": ("tabular",),
    "json": ("record", "tabular"),
    "xml": ("record", "tabular"),
    "pptx": ("presentation",),
    "ics": ("calendar",),
    "vcf": ("contact",),
}

#: Preferred renderers for landing the final bytes exactly (resolution A3):
#: txt first, then log, then the storage payload (phase 5).
FINALIZER_PREFERENCE: tuple[str, ...] = ("txt", "log", "dat")

#: Below this many remaining bytes a run stops rather than emitting dust.
MIN_FINALIZER_BYTES = 16

#: Fallback range when neither profile nor defaults know a format.
_FALLBACK_RANGE = SizeRange(4 << 10, 64 << 10)

_TABULAR = frozenset({"csv", "xlsx"})
_RECORD = frozenset({"json", "xml"})


@dataclass(frozen=True)
class PlannedFile:
    """One file the engine will render."""

    index: int
    relative_path: str
    renderer_id: str
    template_id: str | None
    desired_size: int
    seed: int


def plan_seed(master_seed: int) -> int:
    """Domain-separated seed for the planner's own RNG."""
    digest = hashlib.sha256(f"chaff-plan-seed:v1:{master_seed}".encode()).digest()
    return int.from_bytes(digest[:16], "big")


def estimate_file_count(target_bytes: int, pool: dict[str, int]) -> int:
    """Estimated file count for a target volume given a format pool.

    Standalone (not a method) because the engine needs the estimate to size
    the world *before* the planner, which needs the world, exists.
    """
    if target_bytes <= 0:
        return 0
    total_weight = sum(pool.values())
    if total_weight == 0:
        return 0
    avg = (
        sum(weight * DEFAULT_AVG_SIZES.get(fmt, 8 << 10) for fmt, weight in pool.items())
        / total_weight
    )
    return max(1, round(target_bytes / avg))


class Planner:
    """Seeded file-plan generator bound to one run's config and pack."""

    def __init__(
        self,
        config: GenerationConfig,
        profile: Profile,
        bank: ChaffBank,
        world: GenerationWorld,
        templates: TemplateRegistry,
        capabilities: dict[str, RendererCapabilities],
    ) -> None:
        self._config = config
        self._profile = profile
        self._bank = bank
        self._world = world
        self._templates = templates
        self._capabilities = capabilities
        self._rng = random.Random(plan_seed(config.seed))
        self._allocator = PathAllocator()
        self._pool = self._resolve_pool()
        if not self._pool:
            from chaff_generator.core.errors import ConfigurationError

            raise ConfigurationError("No enabled file formats remain after filtering")
        self._project_names = [
            sanitize_filename(project.name, max_length=48) for project in world.projects
        ]
        self._departments = [
            sanitize_filename(department, max_length=48)
            for department in (world.organization.departments or ())
        ]

    # -- planning ----------------------------------------------------------

    def estimate_files(self, target_bytes: int) -> int:
        """Estimated file count for a target volume (drives the §25 warning)."""
        return estimate_file_count(target_bytes, self._pool)

    def next_file(self, index: int, remaining: int) -> PlannedFile | None:
        """Plan file ``index`` given ``remaining`` bytes, or None to stop.

        Returns None when the remainder is smaller than the dust threshold —
        the engine records a warning instead of emitting a microscopic file.
        """
        if remaining < MIN_FINALIZER_BYTES:
            return None
        fmt, desired = self._pick_format_and_size(remaining)
        template = self._pick_template(fmt)
        relative = self._allocate_path(fmt, template.id if template else None, index)
        return PlannedFile(
            index=index,
            relative_path=relative.as_posix(),
            renderer_id=fmt,
            template_id=template.id if template else None,
            desired_size=desired,
            seed=derive_file_seed(self._config.seed, index),
        )

    # -- internals ----------------------------------------------------------

    def _resolve_pool(self) -> dict[str, int]:
        """Effective format pool: config overrides profile when non-empty."""
        if self._config.file_types:
            pool = {
                fmt: setting.weight
                for fmt, setting in self._config.file_types.items()
                if setting.enabled and fmt in self._capabilities
            }
            return pool
        return {
            fmt: weight
            for fmt, weight in self._profile.format_weights.items()
            if fmt in self._capabilities
        }

    def _is_exact(self, fmt: str) -> bool:
        caps = self._capabilities.get(fmt)
        return caps is not None and caps.supports_exact_size

    def _pick_format_and_size(self, remaining: int) -> tuple[str, int]:
        fmt = self._weighted_choice()
        lo, hi = self._size_range(fmt)
        desired = _log_uniform(self._rng, lo, hi)
        if desired < remaining:
            return fmt, desired
        # The draw met or passed the remainder: land exactly if we can.
        if self._is_exact(fmt):
            return fmt, remaining
        finalizer = self._pick_finalizer()
        if finalizer is not None:
            return finalizer, remaining
        # No exact renderer available: approximate the tail (may overshoot).
        return fmt, min(desired, remaining)

    def _pick_finalizer(self) -> str | None:
        for fmt in FINALIZER_PREFERENCE:
            if fmt in self._pool and self._is_exact(fmt):
                return fmt
        return None

    def _weighted_choice(self) -> str:
        weights = self._pool
        total = sum(weights.values())
        draw = self._rng.randrange(total)
        for fmt, weight in weights.items():
            draw -= weight
            if draw < 0:
                return fmt
        return next(iter(weights))

    def _size_range(self, fmt: str) -> tuple[int, int]:
        size_range = self._profile.size_profile.get(fmt) or DEFAULT_SIZE_RANGES.get(fmt)
        if size_range is None:
            size_range = _FALLBACK_RANGE
        return size_range.min_bytes, max(size_range.min_bytes, size_range.max_bytes)

    def _pick_template(self, fmt: str) -> TemplateDef | None:
        kinds = TEMPLATE_KINDS.get(fmt)
        if not kinds:
            return None
        rng = self._rng
        for kind in kinds:
            candidates = [
                template
                for template in self._templates.for_kind(kind)
                if kind != "prose" or not template.render_targets or fmt in template.render_targets
            ]
            if not candidates:
                candidates = self._templates.for_kind(kind)
            if candidates:
                return gen.pick(rng, candidates)
        return None

    def _allocate_path(self, fmt: str, template_id: str | None, index: int) -> PurePosixPath:
        directory = self._directory_for(fmt, index)
        if fmt == "dev":
            extension = DEV_EXTENSIONS[index % len(DEV_EXTENSIONS)]
        else:
            extension = EXTENSIONS.get(fmt, "")
        stem = self._stem_for(fmt, template_id, extension, index)
        filename = f"{stem}.{extension}" if extension else stem
        return self._allocator.allocate(directory, sanitize_filename(filename, max_length=96))

    def _directory_for(self, fmt: str, index: int) -> PurePosixPath:
        rng = self._rng
        layout = self._config.directory_layout
        if layout is LayoutMode.FLAT:
            return PurePosixPath("")
        if layout is LayoutMode.SIMPLE:
            if fmt in _TABULAR:
                return PurePosixPath("Spreadsheets")
            if fmt == "log":
                return PurePosixPath("Logs")
            if fmt in _RECORD or fmt == "dat":
                return PurePosixPath("Data")
            if fmt == "dev":
                return PurePosixPath("Code")
            if fmt == "eml":
                return PurePosixPath("Mail")
            if fmt in ("ics", "vcf"):
                return PurePosixPath("Personal")
            return PurePosixPath("Documents")
        # REALISTIC: world-derived folders.
        if fmt == "log":
            return PurePosixPath("Logs")
        if fmt == "dat":
            return PurePosixPath("Data")
        if fmt == "dev":
            return PurePosixPath(("src", "db", "deploy", "docs")[index % 4])
        if fmt == "eml":
            return PurePosixPath("Mail") / "inbox"
        if fmt == "ics":
            return PurePosixPath("Calendar")
        if fmt == "vcf":
            return PurePosixPath("Contacts")
        if fmt in _TABULAR:
            options = ["Finance", "Reports", *_project_dirs(self._project_names)]
            return PurePosixPath(rng.choice(options))
        if fmt in _RECORD:
            options = ["Records", *_project_dirs(self._project_names)]
            return PurePosixPath(rng.choice(options))
        options = [
            "Documents",
            "Reports",
            *_project_dirs(self._project_names),
            *_dept_dirs(self._departments),
        ]
        return PurePosixPath(rng.choice(options))

    def _stem_for(self, fmt: str, template_id: str | None, extension: str, index: int) -> str:
        rng = self._rng
        if template_id:
            stem = template_id.split(".", 1)[1].replace("_", " ").title()
            variant = rng.randrange(3)
            if variant == 0:
                return stem
            if variant == 1:
                return f"{rng.randrange(2023, 2027)} {stem}"
            return f"{stem} - {rng.choice(('draft', 'final', 'review', 'v2'))}"
        if fmt == "log":
            tech = gen.pick(rng, self._bank.words("technologies")).lower().replace(" ", "-")
            month = rng.randrange(1, 13)
            return f"{tech}-{rng.randrange(2023, 2027)}{month:02d}"
        if fmt == "dat":
            return f"payload-{index:05d}"
        if fmt == "dev":
            return _dev_stem(self._bank, extension, rng)
        # Self-generated prose fallback.
        adjective = gen.pick(rng, self._bank.words("adjectives")).title()
        noun = gen.pick(rng, self._bank.words("nouns")).title()
        return f"{adjective} {noun} Notes"


def _project_dirs(names: list[str]) -> list[str]:
    return [f"Projects/{name}" for name in names]


def _dept_dirs(names: list[str]) -> list[str]:
    return [f"Departments/{name}" for name in names]


def _log_uniform(rng: random.Random, low: int, high: int) -> int:
    """Draw a file size log-uniformly: small files common, huge files rare.

    Real filesystems are heavy-tailed; a uniform draw would make every file
    the range's average and a 20 MiB run would be two files.
    """
    if high <= low:
        return high
    span = math.log(high) - math.log(low)
    return int(math.exp(math.log(low) + rng.random() * span))


def _dev_stem(bank: ChaffBank, extension: str, rng: random.Random) -> str:
    noun = gen.pick(rng, bank.words("nouns")).replace(" ", "_").lower()
    if extension == "py":
        return f"{noun}_service"
    if extension == "sql":
        return f"migrate_{noun}"
    if extension in ("yaml", "yml"):
        tech = gen.pick(rng, bank.words("technologies")).lower().replace(" ", "-")
        return f"{tech}-service"
    if extension == "toml":
        return f"{noun}-project"
    if extension == "md":
        return rng.choice(("README", "NOTES", "CONTRIBUTING"))
    return "Dockerfile"

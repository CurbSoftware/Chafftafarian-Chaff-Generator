"""ChaffBank pack loading and validation (spec sections 12-14, 52).

A pack is a directory with ``pack.yaml`` plus ``words/``, ``phrases/``,
``sentences/``, ``entities/``, ``templates/``, and ``profiles/`` subdirectories.
Banks are loaded lazily and cached; text bank files skip blank lines and
``#`` comments. Packs are data, treated as untrusted input.
"""

from __future__ import annotations

import json
import logging
import zipfile
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from chaff_generator.core.errors import PackError
from chaff_generator.profiles.loader import load_profiles
from chaff_generator.profiles.models import Profile
from chaff_generator.templates.loader import load_templates
from chaff_generator.templates.models import TemplateRegistry

logger = logging.getLogger(__name__)

PACK_MANIFEST_NAME = "pack.yaml"

#: ZIP import limits (spec section 52): reject archives that try to expand
#: into unreasonable sizes or file counts.
MAX_PACK_FILES = 5_000
MAX_PACK_TOTAL_BYTES = 200 * 1024 * 1024


@dataclass(frozen=True)
class PackManifest:
    id: str
    name: str
    version: str
    language: str
    description: str = ""
    author: str = ""
    minimum_chaff_version: str = ""
    attribution: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PackManifest:
        try:
            return cls(
                id=str(data["id"]),
                name=str(data["name"]),
                version=str(data["version"]),
                language=str(data.get("language", "en")),
                description=str(data.get("description", "")),
                author=str(data.get("author", "")),
                minimum_chaff_version=str(data.get("minimum_chaff_version", "")),
                attribution=str(data.get("attribution", "")),
            )
        except KeyError as exc:
            raise PackError(f"pack.yaml is missing required key: {exc}") from exc


@dataclass
class PackInfo:
    """Lightweight pack description used by listings (CLI/GUI)."""

    manifest: PackManifest
    path: Path
    source: str  # "builtin" | "user"
    enabled: bool = True


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


class ChaffBank:
    """Loaded, lazily-cached access to one pack's content banks."""

    def __init__(self, root: Path, manifest: PackManifest) -> None:
        self.root = root
        self.manifest = manifest
        self._text_cache: dict[tuple[str, str], tuple[str, ...]] = {}
        self._json_cache: dict[str, Any] = {}
        self._templates: TemplateRegistry | None = None
        self._profiles: dict[str, Profile] | None = None

    # -- text banks ---------------------------------------------------------

    def _load_text_bank(self, category_dir: str, category: str) -> tuple[str, ...]:
        cache_key = (category_dir, category)
        if cache_key in self._text_cache:
            return self._text_cache[cache_key]
        path = self.root / category_dir / f"{category}.txt"
        if not path.is_file():
            raise PackError(
                f"Unknown {category_dir.rstrip('s')} bank: {category!r}",
                details={"pack": self.manifest.id},
            )
        lines: list[str] = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#"):
                lines.append(line)
        bank = tuple(lines)
        self._text_cache[cache_key] = bank
        return bank

    def words(self, category: str) -> tuple[str, ...]:
        return self._load_text_bank("words", category)

    def phrases(self, category: str) -> tuple[str, ...]:
        return self._load_text_bank("phrases", category)

    def sentences(self, category: str) -> tuple[str, ...]:
        return self._load_text_bank("sentences", category)

    # -- entity banks -------------------------------------------------------

    def entity_lines(self, name: str) -> tuple[str, ...]:
        """Load ``entities/<name>.txt``; falls back to the first string field
        of each row of ``entities/<name>.json`` (e.g. cities.json → city names)."""
        txt_path = self.root / "entities" / f"{name}.txt"
        if txt_path.is_file():
            return self._load_text_bank("entities", name)
        json_data = self.entity_json(name) if self._has_entity_json(name) else None
        if isinstance(json_data, list):
            names: list[str] = []
            for row in json_data:
                if isinstance(row, dict):
                    first_string = next(
                        (value for value in row.values() if isinstance(value, str)), None
                    )
                    if first_string:
                        names.append(first_string)
                elif isinstance(row, str):
                    names.append(row)
            return tuple(names)
        raise PackError(f"Unknown entity bank: {name!r}", details={"pack": self.manifest.id})

    def _has_entity_json(self, name: str) -> bool:
        return (self.root / "entities" / f"{name}.json").is_file()

    def entity_json(self, name: str) -> Any:
        """Load and cache ``entities/<name>.json``."""
        if name not in self._json_cache:
            path = self.root / "entities" / f"{name}.json"
            if not path.is_file():
                raise PackError(
                    f"Unknown entity bank: {name!r}", details={"pack": self.manifest.id}
                )
            try:
                self._json_cache[name] = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise PackError(f"Invalid JSON in entities/{name}.json: {exc}") from exc
        return self._json_cache[name]

    def has_bank(self, category_dir: str, category: str) -> bool:
        """True when a text bank exists (used by validation and GUI previews)."""
        return (self.root / category_dir / f"{category}.txt").is_file()

    # -- templates & profiles ----------------------------------------------

    def templates(self) -> TemplateRegistry:
        if self._templates is None:
            self._templates = load_templates(self.root)
        return self._templates

    def profiles(self) -> dict[str, Profile]:
        if self._profiles is None:
            self._profiles = load_profiles(self.root)
        return self._profiles

    # -- construction --------------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> ChaffBank:
        """Load and validate a pack directory."""
        manifest_path = path / PACK_MANIFEST_NAME
        if not manifest_path.is_file():
            raise PackError(f"Not a ChaffBank pack (missing {PACK_MANIFEST_NAME}): {path}")
        try:
            data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise PackError(f"Invalid pack.yaml in {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise PackError(f"pack.yaml in {path} must be a mapping")
        return cls(root=path, manifest=PackManifest.from_dict(data))


def default_pack_path() -> Path:
    """Filesystem path of the built-in default pack bundled with the package."""
    return Path(str(resources.files("chaff_generator") / "data" / "default-pack"))


def load_default_pack() -> ChaffBank:
    """Load the built-in default ChaffBank."""
    return ChaffBank.load(default_pack_path())


# ---------------------------------------------------------------------------
# Validation


@dataclass
class _BankCounts:
    words: int = 0
    phrases: int = 0
    sentences: int = 0
    entities: int = 0


def validate_pack(path: Path) -> ValidationReport:
    """Full structural validation of a pack directory (errors + warnings)."""
    report = ValidationReport()
    try:
        bank = ChaffBank.load(path)
    except PackError as exc:
        report.errors.append(str(exc))
        return report

    counts = _BankCounts()
    for subdir, counter_name in (
        ("words", "words"),
        ("phrases", "phrases"),
        ("sentences", "sentences"),
        ("entities", "entities"),
    ):
        directory = path / subdir
        if not directory.is_dir():
            report.warnings.append(f"Missing directory: {subdir}/")
            continue
        count = len({*directory.glob("*.txt"), *directory.glob("*.json")})
        setattr(counts, counter_name, count)
        if count == 0:
            report.warnings.append(f"Empty directory: {subdir}/")

    if counts.words == 0:
        report.errors.append("Pack contains no word banks at all")
    if counts.sentences == 0:
        report.warnings.append("Pack contains no sentence banks")

    try:
        registry = bank.templates()
        if len(registry) == 0:
            report.warnings.append("Pack contains no templates")
    except Exception as exc:
        report.errors.append(f"Template loading failed: {exc}")

    try:
        profiles = bank.profiles()
        if not profiles:
            report.warnings.append("Pack contains no profiles")
    except Exception as exc:
        report.errors.append(f"Profile loading failed: {exc}")

    for json_file in (
        sorted((path / "entities").glob("*.json")) if (path / "entities").is_dir() else []
    ):
        try:
            json.loads(json_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report.errors.append(f"Invalid JSON: {json_file.name}: {exc}")

    return report


# ---------------------------------------------------------------------------
# Pack management (builtin + user packs)


class PackManager:
    """Lists and imports packs: the builtin default plus user pack folders."""

    def __init__(self, user_packs_dir: Path | None = None) -> None:
        if user_packs_dir is None:
            from platformdirs import user_data_dir

            user_packs_dir = Path(user_data_dir("chaff-generator")) / "packs"
        self.user_packs_dir = user_packs_dir

    def list_packs(self) -> list[PackInfo]:
        builtin = PackInfo(
            manifest=load_default_pack().manifest,
            path=default_pack_path(),
            source="builtin",
        )
        packs = [builtin]
        if self.user_packs_dir.is_dir():
            for entry in sorted(self.user_packs_dir.iterdir()):
                if not entry.is_dir():
                    continue
                manifest_path = entry / PACK_MANIFEST_NAME
                if not manifest_path.is_file():
                    continue
                try:
                    bank = ChaffBank.load(entry)
                except PackError:
                    logger.warning("Skipping invalid user pack: %s", entry)
                    continue
                packs.append(PackInfo(manifest=bank.manifest, path=entry, source="user"))
        return packs

    def import_zip(self, zip_path: Path, dest_name: str | None = None) -> PackInfo:
        """Import a pack ZIP with full zip-slip protection (spec section 52)."""
        name = dest_name or zip_path.stem
        name = name.replace(" ", "-")
        dest = self.user_packs_dir / name
        if dest.exists():
            raise PackError(f"A pack named {name!r} already exists")

        try:
            with zipfile.ZipFile(zip_path) as archive:
                entries = archive.infolist()
                if len(entries) > MAX_PACK_FILES:
                    raise PackError(
                        f"Archive has too many entries ({len(entries)} > {MAX_PACK_FILES})"
                    )
                total = sum(entry.file_size for entry in entries)
                if total > MAX_PACK_TOTAL_BYTES:
                    raise PackError(f"Archive expands beyond the {MAX_PACK_TOTAL_BYTES}-byte limit")
                self.user_packs_dir.mkdir(parents=True, exist_ok=True)
                dest.mkdir()
                for entry in entries:
                    self._safe_extract(archive, entry, dest)
        except zipfile.BadZipFile as exc:
            raise PackError(f"Not a valid ZIP archive: {zip_path}") from exc

        try:
            bank = ChaffBank.load(dest)
        except PackError as exc:
            import shutil

            shutil.rmtree(dest, ignore_errors=True)
            raise PackError(f"Imported archive is not a valid pack: {exc}") from exc
        return PackInfo(manifest=bank.manifest, path=dest, source="user")

    def _safe_extract(self, archive: zipfile.ZipFile, entry: zipfile.ZipInfo, dest: Path) -> None:
        """Extract one entry, rejecting traversal, absolute paths, drives, symlinks."""
        if entry.is_dir():
            return
        candidate = PurePosixPath(entry.filename)
        if candidate.is_absolute() or entry.filename.startswith(("/", "\\")):
            raise PackError(f"Archive entry has an absolute path: {entry.filename}")
        if ".." in candidate.parts or "<" in entry.filename or ">" in entry.filename:
            raise PackError(f"Archive entry escapes the pack directory: {entry.filename}")
        if entry.filename[1:2] == ":":  # drive-letter path
            raise PackError(f"Archive entry has a drive-letter path: {entry.filename}")
        if entry.external_attr >> 16 & 0o170000 == 0o120000:  # S_IFLNK
            raise PackError(f"Archive entry is a symlink: {entry.filename}")

        target = dest.joinpath(*candidate.parts)
        if not target.resolve().is_relative_to(dest.resolve()):
            raise PackError(f"Archive entry escapes the pack directory: {entry.filename}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(entry) as source, target.open("wb") as sink:
            remaining = entry.file_size
            while remaining > 0:
                chunk = source.read(min(1 << 20, remaining))
                if not chunk:
                    break
                sink.write(chunk)
                remaining -= len(chunk)

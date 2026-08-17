"""ChaffEngine: the run lifecycle (spec sections 10, 21-22, 26-27, 46).

One engine instance performs one run: preflight, generate, then (from the
GUI thread) pause / resume / cancel. Per-file pipeline:

    plan → build context (isolated seeded RNG + sandboxed template engine)
         → render to ``.<name>.chaff-partial``
         → close → hash → ``os.replace`` onto the final path
         → journal append → events

Events are published through a plain callback (frozen dataclasses, no Qt) so
the CLI and the GUI worker can both observe progress. Content dates come
from the configured date range; the run-root timestamp is run *identity*,
not content, and is the only wall-clock value in the system.
"""

from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from chaff_generator.content import builders
from chaff_generator.content.bank import ChaffBank, load_default_pack
from chaff_generator.content.context import RenderContext
from chaff_generator.content.template_engine import ChaffTemplateEngine
from chaff_generator.content.world import build_world
from chaff_generator.core import events as event_types
from chaff_generator.core.errors import ChaffError, ConfigurationError, InsufficientSpaceError
from chaff_generator.core.events import FILE_EVENT_MIN_BYTES, PROGRESS_INTERVAL_S
from chaff_generator.core.filesystem import FreeSpaceMonitor, atomic_replace, check_writable_dir
from chaff_generator.core.hashing import hash_file
from chaff_generator.core.models import (
    GenerationResult,
    PreflightSummary,
    RunStatus,
    TargetMode,
)
from chaff_generator.core.paths import safe_join
from chaff_generator.core.planner import Planner, estimate_file_count
from chaff_generator.core.seeding import derive_file_seed
from chaff_generator.core.size import format_size
from chaff_generator.manifest.models import FileRecord, RunMarker
from chaff_generator.manifest.writer import (
    JournalWriter,
    new_manifest,
    write_manifest,
    write_run_marker,
)
from chaff_generator.profiles.loader import resolve_profile
from chaff_generator.renderers import build_registry
from chaff_generator.templates.models import TemplateDef
from chaff_generator.version import __version__

if TYPE_CHECKING:
    from chaff_generator.content.world import GenerationWorld
    from chaff_generator.core.events import ChaffEvent, EventCallback
    from chaff_generator.core.models import GenerationConfig
    from chaff_generator.core.planner import PlannedFile
    from chaff_generator.renderers.documents import SemanticDocument

    DocumentBuilder = Callable[[TemplateDef, RenderContext], SemanticDocument]

#: Stop planning new files after this many consecutive per-file failures.
MAX_CONSECUTIVE_FAILURES = 20

#: Hard ceiling on files in one run (a runaway-loop backstop).
MAX_FILES_PER_RUN = 1_000_000

#: Warn (spec section 25) when a run would exceed this many files.
FILE_COUNT_WARN_THRESHOLD = 100_000

#: Fill-mode headroom: the run's own marker and journal grow while writing;
#: aiming this far shy of full availability keeps the reserve intact.
_FILL_HEADROOM_BYTES = 64 << 10

#: Template kinds with a semantic-document builder; other kinds self-render.
_BUILDER_BY_KIND: dict[str, DocumentBuilder] = {
    "prose": builders.build_prose_document,
    "tabular": builders.build_tabular_document,
    "presentation": builders.build_presentation_document,
    "record": builders.build_record_collection,
}


class ChaffEngine:
    """GUI-free generation engine; one instance performs one run."""

    def __init__(
        self,
        config: GenerationConfig,
        bank: ChaffBank | None = None,
        event_callback: EventCallback | None = None,
    ) -> None:
        self._config = config
        self._bank = bank if bank is not None else load_default_pack()
        self._emit_cb = event_callback
        self._lock = threading.Lock()
        self._status = RunStatus.PLANNING
        self._pause_gate = threading.Event()
        self._cancel_requested = threading.Event()
        self._registry = build_registry()
        self._last_progress = 0.0
        self._file_event_times: list[float] = []
        self._run_id: str = ""
        self._world: GenerationWorld | None = None

    # ------------------------------------------------------------------ state

    @property
    def status(self) -> RunStatus:
        with self._lock:
            return self._status

    def pause(self) -> None:
        """Request a pause; the run parks at the next file boundary."""
        with self._lock:
            if self._status is RunStatus.RUNNING:
                self._status = RunStatus.PAUSED
                self._pause_gate.set()

    def resume(self) -> None:
        """Clear a pending pause; parked runs continue."""
        was_paused = self._pause_gate.is_set()
        self._pause_gate.clear()
        with self._lock:
            if self._status is RunStatus.PAUSED:
                self._status = RunStatus.RUNNING
        if was_paused:
            self._emit(event_types.RunResumed(run_id=self._run_id))

    def cancel(self) -> None:
        """Request cancellation; the run stops at the next boundary."""
        self._cancel_requested.set()
        self._pause_gate.clear()  # wake a parked run so it can exit

    # ---------------------------------------------------------------- preflight

    def preflight(self) -> PreflightSummary:
        """Validate the target and plan without writing anything."""
        warnings: list[str] = []
        target = self._config.target
        check_writable_dir(target.path)
        monitor = FreeSpaceMonitor(target.path, reserve_bytes=target.reserve)
        free_bytes = monitor.check()

        if target.mode is TargetMode.EXACT:
            requested = target.amount or 0
        else:
            requested = self._fill_target(monitor)
        if target.mode is not TargetMode.EXACT and requested <= 0:
            raise InsufficientSpaceError(
                "No space is available above the reserve for a fill-mode run",
                details={"free_bytes": free_bytes, "reserve_bytes": target.reserve},
            )

        pool = self._resolve_pool(warnings)
        if not pool:
            raise ConfigurationError(
                "No usable file formats: every format failed to load its renderer"
            )

        estimated = estimate_file_count(requested, pool)
        if estimated > FILE_COUNT_WARN_THRESHOLD:
            warnings.append(
                f"This job is estimated to create ~{estimated:,} files "
                f"(more than {FILE_COUNT_WARN_THRESHOLD:,}); expect slow runs and "
                "high inode use"
            )

        projected = monitor.available_for_chaff() - requested
        if projected < 0:
            raise InsufficientSpaceError(
                "Not enough free space for the requested volume",
                details={
                    "free_bytes": free_bytes,
                    "reserve_bytes": target.reserve,
                    "requested_bytes": requested,
                },
            )

        return PreflightSummary(
            target_path=target.path,
            free_bytes=free_bytes,
            requested_bytes=requested,
            projected_remaining_bytes=max(projected, 0),
            estimated_file_count=estimated,
            formats=sorted(pool),
            profile_id=self._config.profile,
            seed=self._config.seed,
            completion=self._config.completion,
            manifest_enabled=self._config.integrity.create_manifest,
            warnings=warnings,
        )

    # ---------------------------------------------------------------- generate

    def generate(self) -> GenerationResult:
        """Run the full generation job and return its result."""
        with self._lock:
            if self._status is not RunStatus.PLANNING:
                raise ChaffError(f"Engine already ran (status {self._status.value})")
            self._status = RunStatus.RUNNING

        started = time.monotonic()
        warnings: list[str] = []
        target = self._config.target

        pool = self._resolve_pool(warnings)
        if not pool:
            return self._fail_before_run(
                "No usable file formats: every format failed to load its renderer", warnings
            )
        capabilities = {fmt: self._registry.get(fmt).capabilities for fmt in pool}

        check_writable_dir(target.path)
        monitor = FreeSpaceMonitor(target.path, reserve_bytes=target.reserve)
        free_at_start = monitor.check()
        requested = self._fill_target(monitor)
        if requested <= 0:
            return self._fail_before_run(
                "No space is available above the reserve for this run", warnings
            )
        if monitor.available_for_chaff() < requested:
            return self._fail_before_run(
                "Free space dropped below the requested volume before writing", warnings
            )

        run_root = self._make_run_root(target.path)
        self._run_id = run_root.name
        created_at = _run_timestamp()
        write_run_marker(
            run_root,
            RunMarker(run_id=self._run_id, created_at=created_at, app_version=__version__),
        )

        profile = resolve_profile(self._config.profile, self._bank.profiles())
        if target.mode is not TargetMode.EXACT:
            # The run marker is real overhead: re-aim the fill target now
            # that it exists, so the first draw does not clamp to a size
            # that no longer fits above the reserve.
            requested = self._fill_target(monitor)
        estimated = estimate_file_count(requested, pool)
        self._world = build_world(
            self._config.seed, self._config, self._bank, estimated_files=estimated
        )
        assert self._world is not None  # set two lines above; narrows for callers
        planner = Planner(
            config=self._config,
            profile=profile,
            bank=self._bank,
            world=self._world,
            templates=self._bank.templates(),
            capabilities=capabilities,
        )

        manifest = new_manifest(
            run_id=self._run_id,
            created_at=created_at,
            app_version=__version__,
            target_bytes=requested,
            profile=profile.id,
            pack_id=self._bank.manifest.id,
            pack_version=self._bank.manifest.version,
            seed=self._config.seed,
        )
        journal = JournalWriter(run_root)
        journal.append_event("run_started", run_id=self._run_id, target_bytes=requested)

        self._emit(
            event_types.RunStarted(
                run_id=self._run_id,
                run_root=run_root,
                target_bytes=requested,
                free_bytes=free_at_start,
            )
        )

        files_created = 0
        bytes_written = 0
        remaining = requested
        index = 0
        consecutive_failures = 0
        error: str | None = None
        index_overflow = False

        while remaining > 0:
            if self._cancel_requested.is_set():
                break
            self._park_if_paused()
            if self._cancel_requested.is_set():
                break
            if index >= MAX_FILES_PER_RUN:
                index_overflow = True
                break
            planned = planner.next_file(index, remaining)
            if planned is None:
                warnings.append(
                    f"Stopped with {remaining} bytes unallocated (below the minimum "
                    "finalizer size); the run falls short of the exact target"
                )
                break
            try:
                record, written = self._render_file(run_root, planned, monitor)
            except InsufficientSpaceError as exc:
                if target.mode is TargetMode.EXACT:
                    error = f"Ran out of free space (respecting the reserve): {exc}"
                else:
                    # Fill modes: reaching the reserve IS the goal. Whatever
                    # gap remains cannot be filled without crossing it
                    # (spec section 26), so the run completes gracefully.
                    warnings.append(
                        "Filled to the reserve; the last "
                        f"{format_size(remaining)} gap cannot be written without "
                        "crossing it"
                    )
                break
            except (ChaffError, OSError) as exc:
                consecutive_failures += 1
                self._emit(
                    event_types.FileFailed(
                        index=planned.index,
                        relative_path=planned.relative_path,
                        error=str(exc),
                    )
                )
                warnings.append(
                    f"File {planned.relative_path} failed: {exc.__class__.__name__}: {exc}"
                )
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    error = "Too many consecutive file failures; stopping"
                    break
                index += 1
                continue
            consecutive_failures = 0
            journal.append_file(record)
            manifest.files.append(record)
            manifest.bytes_written += written

            files_created += 1
            bytes_written += written
            if target.mode is TargetMode.FILL_UNTIL_RESERVE:
                # Monitor truth wins (spec section 58): foreign writers and
                # our own output both count against what remains.
                remaining = monitor.available_for_chaff()
            else:
                remaining = max(0, remaining - written)
            self._emit(
                event_types.FileCompleted(
                    index=planned.index,
                    relative_path=planned.relative_path,
                    size=written,
                    sha256=record.sha256,
                )
            )
            self._maybe_progress(bytes_written, requested, files_created, planned, monitor)
            index += 1

        if index_overflow:
            error = f"File ceiling of {MAX_FILES_PER_RUN} reached before the target volume"

        free_after = monitor.check()
        if self._cancel_requested.is_set():
            status = RunStatus.CANCELLED
            self._emit(event_types.RunCancelled(run_id=self._run_id))
        elif error is not None:
            status = RunStatus.FAILED
        else:
            status = RunStatus.COMPLETED

        manifest.status = status.value
        manifest.free_bytes_after = free_after
        journal.append_event(
            "run_finished",
            run_id=self._run_id,
            status=status.value,
            files=files_created,
            bytes=bytes_written,
        )
        journal.close()
        manifest_path: Path | None = None
        if self._config.integrity.create_manifest:
            manifest_path = write_manifest(run_root, manifest)

        duration = max(time.monotonic() - started, 0.001)
        result = GenerationResult(
            run_id=self._run_id,
            run_root=run_root,
            status=status,
            files_created=files_created,
            bytes_written=bytes_written,
            duration_s=duration,
            throughput_bps=bytes_written / duration,
            manifest_path=manifest_path,
            warnings=warnings,
            error=error,
        )
        with self._lock:
            self._status = status
        self._emit(event_types.RunCompleted(status=status, result=result, run_root=run_root))
        return result

    # ---------------------------------------------------------------- internals

    def _fill_target(self, monitor: FreeSpaceMonitor) -> int:
        """Bytes this run aims to write under the configured target mode.

        EXACT uses the configured amount. PERCENT_FREE fills ``percent``% of
        the currently free space. FILL_UNTIL_RESERVE aims at everything above
        the reserve; the loop re-reads the monitor each file so foreign
        writers and the run's own output both shrink the remaining target.
        """
        target = self._config.target
        if target.mode is TargetMode.EXACT:
            return target.amount or 0
        available = monitor.available_for_chaff()
        if target.mode is TargetMode.PERCENT_FREE:
            return int(available * float(target.percent or 0) / 100)
        # Aim shy of the full availability: the run's own marker/journal
        # grow while writing, and the reserve must never be crossed.
        return max(0, available - _FILL_HEADROOM_BYTES)

    def _resolve_pool(self, warnings: list[str]) -> dict[str, int]:
        """Effective format pool with renderer availability probed."""
        if self._config.file_types:
            candidates = {
                fmt: setting.weight
                for fmt, setting in self._config.file_types.items()
                if setting.enabled
            }
        else:
            profile = resolve_profile(self._config.profile, self._bank.profiles())
            candidates = dict(profile.format_weights)
        pool: dict[str, int] = {}
        for fmt, weight in candidates.items():
            try:
                self._registry.get(fmt)
            except ChaffError as exc:
                warnings.append(f"Format {fmt!r} unavailable and skipped: {exc}")
                continue
            pool[fmt] = max(weight, 1)
        return pool

    def _render_file(
        self, run_root: Path, planned: PlannedFile, monitor: FreeSpaceMonitor
    ) -> tuple[FileRecord, int]:
        """Render one planned file; returns its manifest record and size."""
        if monitor.would_violate_reserve(planned.desired_size):
            raise InsufficientSpaceError(
                "Writing this file would cross the reserve",
                details={"planned_bytes": planned.desired_size},
            )
        assert self._world is not None

        final_path = safe_join(run_root, planned.relative_path)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        partial_path = final_path.parent / f".{final_path.name}.chaff-partial"

        rng = random.Random(planned.seed)
        engine = ChaffTemplateEngine(world=self._world, bank=self._bank, rng=rng)
        context = RenderContext(
            rng=rng,
            world=self._world,
            bank=self._bank,
            template_engine=engine,
            desired_size=planned.desired_size,
            run_id=self._run_id,
            app_version=__version__,
            template_id=planned.template_id,
            file_seed=planned.seed,
        )
        context.extra["final_suffix"] = final_path.suffix.lstrip(".").lower()
        context.extra["final_stem"] = final_path.stem

        document = self._build_document(planned, context)
        renderer = self._registry.get(planned.renderer_id)
        self._maybe_file_started(planned)
        result = renderer.render(document, partial_path, context)
        digest = result.sha256 if result.sha256 else hash_file(partial_path)
        atomic_replace(partial_path, final_path)
        record = FileRecord(
            relative_path=planned.relative_path,
            size=result.size,
            sha256=digest,
            renderer=planned.renderer_id,
            template_id=planned.template_id,
            seed=planned.seed,
        )
        return record, result.size

    def _build_document(
        self, planned: PlannedFile, context: RenderContext
    ) -> SemanticDocument | None:
        if planned.template_id is None:
            return None
        template = self._bank.templates().require(planned.template_id)
        builder = _BUILDER_BY_KIND.get(template.kind)
        if builder is None:
            return None  # kinds without builders (email/calendar/contact) self-render
        return builder(template, context)

    def _make_run_root(self, target_path: Path) -> Path:
        """Create ``Chaff_Run_YYYYMMDD_HHMMSS_<4hex>`` under the target."""
        rng = random.Random(derive_file_seed(self._config.seed, 0))
        stamp = time.strftime("%Y%m%d_%H%M%S")
        run_root = target_path / f"Chaff_Run_{stamp}_{rng.getrandbits(16):04x}"
        while run_root.exists():  # same second, same seed: draw new entropy
            run_root = target_path / f"Chaff_Run_{stamp}_{rng.getrandbits(16):04x}"
        run_root.mkdir(parents=True)
        return run_root

    def _park_if_paused(self) -> None:
        if not self._pause_gate.is_set():
            return
        self._emit(event_types.RunPaused(run_id=self._run_id))
        while self._pause_gate.is_set() and not self._cancel_requested.is_set():
            time.sleep(0.05)

    def _maybe_file_started(self, planned: PlannedFile) -> None:
        now = time.monotonic()
        if planned.desired_size >= FILE_EVENT_MIN_BYTES or self._file_event_budget(now):
            self._file_event_times.append(now)
            self._emit(
                event_types.FileStarted(
                    index=planned.index,
                    relative_path=planned.relative_path,
                    renderer=planned.renderer_id,
                )
            )

    def _file_event_budget(self, now: float) -> bool:
        """True while per-file events stay under the rate limit (resolution A5)."""
        cutoff = now - 1.0
        self._file_event_times = [t for t in self._file_event_times if t > cutoff]
        return len(self._file_event_times) < 10

    def _maybe_progress(
        self,
        bytes_written: int,
        target_bytes: int,
        files: int,
        planned: PlannedFile,
        monitor: FreeSpaceMonitor,
    ) -> None:
        now = time.monotonic()
        if now - self._last_progress < PROGRESS_INTERVAL_S:
            return
        self._last_progress = now
        self._emit(
            event_types.ProgressUpdated(
                bytes_written=bytes_written,
                target_bytes=target_bytes,
                files=files,
                current_file=planned.relative_path,
                free_bytes=monitor.check(),
                throughput_bps=0.0,
            )
        )

    def _fail_before_run(self, error: str, warnings: list[str]) -> GenerationResult:
        with self._lock:
            self._status = RunStatus.FAILED
        result = GenerationResult(
            run_id="",
            run_root=Path(),
            status=RunStatus.FAILED,
            files_created=0,
            bytes_written=0,
            duration_s=0.0,
            throughput_bps=0.0,
            manifest_path=None,
            warnings=warnings,
            error=error,
        )
        self._emit(
            event_types.RunCompleted(status=RunStatus.FAILED, result=result, run_root=Path())
        )
        return result

    def _emit(self, event: ChaffEvent) -> None:
        if self._emit_cb is not None:
            self._emit_cb(event)


def _run_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")

"""Progress event system shared by the core engine, CLI, and GUI.

The engine publishes plain frozen dataclasses through a callback; the CLI
renders them as terminal lines and the GUI adapts them to Qt signals. No Qt
types appear here (spec section 46).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from chaff_generator.core.models import GenerationResult, RunStatus


@dataclass(frozen=True)
class RunStarted:
    run_id: str
    run_root: Path
    target_bytes: int | None
    free_bytes: int


@dataclass(frozen=True)
class FileStarted:
    index: int
    relative_path: str
    renderer: str


@dataclass(frozen=True)
class FileCompleted:
    index: int
    relative_path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class FileFailed:
    index: int
    relative_path: str
    error: str


@dataclass(frozen=True)
class ProgressUpdated:
    bytes_written: int
    target_bytes: int | None
    files: int
    current_file: str
    free_bytes: int
    throughput_bps: float


@dataclass(frozen=True)
class WarningRaised:
    message: str
    details: str = ""


@dataclass(frozen=True)
class RunPaused:
    run_id: str


@dataclass(frozen=True)
class RunResumed:
    run_id: str


@dataclass(frozen=True)
class RunCancelled:
    run_id: str


@dataclass(frozen=True)
class RunCompleted:
    status: RunStatus
    result: GenerationResult | None
    run_root: Path


ChaffEvent = (
    RunStarted
    | FileStarted
    | FileCompleted
    | FileFailed
    | ProgressUpdated
    | WarningRaised
    | RunPaused
    | RunResumed
    | RunCancelled
    | RunCompleted
)

EventCallback = Callable[[ChaffEvent], None]

#: Minimum interval between ProgressUpdated events (seconds).
PROGRESS_INTERVAL_S: Final[float] = 0.25

#: Per-file events are suppressed for small files beyond this rate (events/second).
FILE_EVENT_MAX_RATE: Final[float] = 10.0

#: Only files at least this large always emit FileStarted/FileCompleted.
FILE_EVENT_MIN_BYTES: Final[int] = 1 << 20

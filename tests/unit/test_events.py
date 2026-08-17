"""Event dataclasses are frozen, typed, and carry the spec-required fields."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from chaff_generator.core import events
from chaff_generator.core.models import RunStatus


def test_events_are_frozen() -> None:
    started = events.RunStarted(
        run_id="r1",
        run_root=Path("/tmp/chaff"),
        target_bytes=1024,
        free_bytes=2048,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        started.run_id = "other"  # type: ignore[misc]


def test_file_completed_carries_hash() -> None:
    done = events.FileCompleted(
        index=3,
        relative_path="docs/report.txt",
        size=1234,
        sha256="ab" * 32,
    )
    assert done.index == 3 and len(done.sha256) == 64


def test_run_completed_optional_result() -> None:
    finished = events.RunCompleted(status=RunStatus.COMPLETED, result=None, run_root=Path("/tmp"))
    assert finished.result is None


def test_event_union_members() -> None:
    for name in (
        "RunStarted",
        "FileStarted",
        "FileCompleted",
        "FileFailed",
        "ProgressUpdated",
        "WarningRaised",
        "RunPaused",
        "RunResumed",
        "RunCancelled",
        "RunCompleted",
    ):
        assert hasattr(events, name)


def test_progress_rate_constants() -> None:
    assert events.PROGRESS_INTERVAL_S >= 0.25
    assert events.FILE_EVENT_MAX_RATE >= 1.0

"""Filesystem helpers: free space, writability, atomic replace (temp dirs only)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from chaff_generator.core.errors import ChaffError, InsufficientSpaceError
from chaff_generator.core.filesystem import (
    FreeSpaceMonitor,
    atomic_replace,
    check_writable_dir,
    free_bytes,
    fsync_dir,
    fsync_file,
    total_bytes,
)


def test_free_bytes_matches_shutil(tmp_path: Path) -> None:
    usage = os.statvfs(tmp_path) if os.name == "posix" else None
    value = free_bytes(tmp_path)
    assert value > 0
    if usage is not None:
        assert value == usage.f_bavail * usage.f_frsize


def test_total_bytes_positive(tmp_path: Path) -> None:
    assert total_bytes(tmp_path) > 0


def test_check_writable_dir_ok(tmp_path: Path) -> None:
    check_writable_dir(tmp_path)  # no exception
    assert not list(tmp_path.glob(".chaff-write-probe-*"))  # probe cleaned up


def test_check_writable_dir_missing() -> None:
    with pytest.raises(ChaffError, match="does not exist"):
        check_writable_dir(Path("/nonexistent/chaff/dir"))


def test_check_writable_dir_is_file(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("x")
    with pytest.raises(ChaffError, match="not a directory"):
        check_writable_dir(target)


def test_atomic_replace(tmp_path: Path) -> None:
    tmp = tmp_path / ".chaff-partial"
    final = tmp_path / "final.txt"
    tmp.write_bytes(b"payload")
    atomic_replace(tmp, final)
    assert final.read_bytes() == b"payload"
    assert not tmp.exists()


def test_fsync_helpers_safe(tmp_path: Path) -> None:
    target = tmp_path / "f.bin"
    with open(target, "wb") as handle:
        handle.write(b"data")
        fsync_file(handle)
    fsync_dir(tmp_path)  # no-op on Windows, real on POSIX


class TestFreeSpaceMonitor:
    def test_check_passes_with_reserve(self, tmp_path: Path) -> None:
        monitor = FreeSpaceMonitor(tmp_path, reserve_bytes=1)
        monitor.check()

    def test_reserve_violation_detected(self, tmp_path: Path) -> None:
        monitor = FreeSpaceMonitor(tmp_path, reserve_bytes=2**70)
        with pytest.raises(InsufficientSpaceError):
            monitor.enforce(0)

    def test_would_violate_reserve(self, tmp_path: Path) -> None:
        monitor = FreeSpaceMonitor(tmp_path, reserve_bytes=1)
        assert monitor.would_violate_reserve(2**70) is True
        assert monitor.would_violate_reserve(1) is False

    def test_enforce_raises_with_context(self, tmp_path: Path) -> None:
        monitor = FreeSpaceMonitor(tmp_path, reserve_bytes=1)
        with pytest.raises(InsufficientSpaceError) as excinfo:
            monitor.enforce(2**70)
        assert "reserve" in str(excinfo.value).lower()

"""Filesystem primitives: capacity, writability, atomic replacement, fsync.

Stdlib-only so behaviour is identical on Windows, Linux, and macOS.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import IO, Final

from chaff_generator.core.errors import ChaffError, InsufficientSpaceError

logger = logging.getLogger(__name__)

#: Default conservative free-space reserve kept on the target filesystem.
DEFAULT_RESERVE_BYTES: Final[int] = 2 * 10**9  # 2 GB

_PROBE_PREFIX: Final = ".chaff-write-probe-"


def free_bytes(path: Path) -> int:
    """Current free space on the filesystem containing ``path``."""
    return shutil.disk_usage(path).free


def total_bytes(path: Path) -> int:
    """Total capacity of the filesystem containing ``path``."""
    return shutil.disk_usage(path).total


def check_writable_dir(path: Path) -> None:
    """Verify ``path`` is an existing writable directory, with plain errors."""
    if not path.exists():
        raise ChaffError(f"Target directory does not exist: {path}")
    if not path.is_dir():
        raise ChaffError(f"Target is not a directory: {path}")
    probe = path / f"{_PROBE_PREFIX}{uuid.uuid4().hex[:8]}"
    try:
        probe.write_text("probe", encoding="utf-8")
        probe.unlink()
    except PermissionError as exc:
        raise ChaffError(
            f"Permission denied writing to {path}. Choose a writable directory "
            "or adjust its permissions.",
        ) from exc
    except OSError as exc:
        raise ChaffError(f"Cannot write to {path}: {exc}") from exc


def atomic_replace(tmp: Path, final: Path) -> None:
    """Atomically move a closed temp file onto its final name."""
    os.replace(tmp, final)


def fsync_file(handle: IO[bytes] | IO[str]) -> None:
    """Flush OS buffers for an open binary file handle to disk."""
    try:
        handle.flush()
        os.fsync(handle.fileno())
    except (AttributeError, OSError):  # non-file objects or unsupported platforms
        logger.debug("fsync_file skipped for %r", handle)


def fsync_dir(path: Path) -> None:
    """fsync a directory entry so a rename survives power loss (POSIX only)."""
    if sys.platform == "win32":
        return
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        logger.debug("fsync_dir could not open %s", path)
        return
    try:
        os.fsync(fd)
    except OSError:
        logger.debug("fsync_dir failed for %s", path)
    finally:
        os.close(fd)


class FreeSpaceMonitor:
    """Tracks free space on one filesystem against a reserve threshold.

    ``check()`` is called repeatedly during generation; the filesystem is the
    source of truth even when other processes are also writing (spec §58).
    """

    def __init__(self, path: Path, reserve_bytes: int) -> None:
        self.path = path
        self.reserve_bytes = max(0, reserve_bytes)
        self._last_free = free_bytes(path)

    @property
    def last_free(self) -> int:
        return self._last_free

    def check(self) -> int:
        """Re-read free space; returns the current value."""
        self._last_free = free_bytes(self.path)
        return self._last_free

    def available_for_chaff(self) -> int:
        """Bytes that may still be written without violating the reserve."""
        return max(0, self.check() - self.reserve_bytes)

    def would_violate_reserve(self, planned_bytes: int) -> bool:
        """True when writing ``planned_bytes`` more would breach the reserve."""
        return self._last_free - planned_bytes < self.reserve_bytes

    def enforce(self, planned_bytes: int) -> None:
        """Raise :class:`InsufficientSpaceError` if the plan breaches reserve."""
        free = self.check()
        if free - planned_bytes < self.reserve_bytes:
            raise InsufficientSpaceError(
                "Writing the planned data would violate the free-space reserve.",
                details={
                    "free_bytes": free,
                    "planned_bytes": planned_bytes,
                    "reserve_bytes": self.reserve_bytes,
                },
            )

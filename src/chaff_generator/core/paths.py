"""Cross-platform path sanitization and containment.

Every filename and directory Chaff generates or touches goes through this
module. Windows rules (reserved device names, illegal characters, trailing
dots/spaces, MAX_PATH awareness) are applied on *all* platforms because
generated files migrate between operating systems. Case-insensitive collision
handling matches NTFS and default APFS behaviour without probing the
filesystem.
"""

from __future__ import annotations

import re
import stat as stat_module
from pathlib import Path, PurePosixPath
from typing import Final

from chaff_generator.core.errors import UnsafePathError

WINDOWS_RESERVED: Final[frozenset[str]] = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

#: Characters Windows forbids in filenames, plus C0 control characters.
ILLEGAL_CHARS: Final[frozenset[str]] = frozenset('<>:"/\\|?*' + "".join(chr(i) for i in range(32)))

WINDOWS_MAX_PATH: Final[int] = 260

#: Conservative per-component cap; keeps full generated paths well short of
#: MAX_PATH even under nested run roots.
DEFAULT_NAME_MAX: Final[int] = 96

_ILLEGAL_RE: Final[re.Pattern[str]] = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+")


def sanitize_filename(name: str, *, max_length: int = DEFAULT_NAME_MAX) -> str:
    """Return a filename safe on Windows, Linux, and macOS.

    Replaces illegal characters with ``-``, collapses whitespace, strips
    leading/trailing dots and spaces, resolves Windows reserved device names,
    and truncates to ``max_length`` while preserving the extension.
    """
    cleaned = _ILLEGAL_RE.sub("-", name.strip())
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    cleaned = cleaned.rstrip(". ")
    if not cleaned:
        cleaned = "untitled"

    stem, dot, suffix = cleaned.partition(".")
    while "." in suffix:  # keep only the final extension
        stem = f"{stem}.{suffix.partition('.')[0]}"
        suffix = suffix.partition(".")[2]
    suffix = f".{suffix}" if dot and suffix else ""

    base, dot_rest, rest = stem.partition(".")
    if stem.upper() in WINDOWS_RESERVED:
        stem = f"{stem}_"
    elif base.upper() in WINDOWS_RESERVED:
        # Windows treats "AUX.tar.gz" like "AUX": rename the base, keep the rest.
        stem = f"{base}_{dot_rest}{rest}" if dot_rest else f"{base}_"

    return truncate_name(f"{stem}{suffix}", max_length)


def truncate_name(name: str, max_length: int) -> str:
    """Truncate a filename to ``max_length`` characters, preserving the extension."""
    if len(name) <= max_length:
        return name
    stem, dot, suffix = name.rpartition(".")
    if dot and len(suffix) <= 10 and stem:
        keep = max(1, max_length - len(suffix) - 1)
        return f"{stem[:keep].rstrip('. ')}.{suffix}"
    return name[:max_length].rstrip(". ")


def sanitize_relative_path(relative: str | PurePosixPath) -> PurePosixPath:
    """Sanitize each segment of a relative path.

    Empty segments and ``.`` are dropped. ``..`` is rejected — containment is
    the caller's job, but a relative path containing traversal never produces
    a usable PurePosixPath anyway.
    """
    if isinstance(relative, str):
        relative = PurePosixPath(relative)
    if relative.is_absolute():
        raise UnsafePathError(f"Relative path expected, got absolute: {relative}")

    segments: list[str] = []
    for part in relative.parts:
        if part in ("", "."):
            continue
        if part == "..":
            raise UnsafePathError(f"Path traversal is not allowed: {relative}")
        segments.append(sanitize_filename(part))
    if not segments:
        raise UnsafePathError("Empty relative path")
    return PurePosixPath(*segments)


def is_within(child: Path, root: Path) -> bool:
    """True when ``child`` (resolved) is ``root`` (resolved) or inside it."""
    try:
        resolved_child = child.resolve()
        resolved_root = root.resolve()
    except OSError:  # e.g. path with NUL bytes or unreachable on this OS
        return False
    return resolved_child == resolved_root or resolved_root in resolved_child.parents


def safe_join(root: Path, relative: str | PurePosixPath) -> Path:
    """Join ``root`` with a sanitized relative path, verifying containment.

    Walks each parent level with ``lstat`` so a symlinked directory inside the
    run can never redirect a write outside the run root. Raises
    :class:`UnsafePathError` on absolute paths, drive letters, traversal, or
    symlink escape.
    """
    clean = sanitize_relative_path(relative)

    root_resolved = root.resolve()
    candidate = root
    for segment in clean.parts:
        candidate = candidate / segment
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue  # not created yet; the final containment check governs
        except OSError as exc:
            raise UnsafePathError(
                f"Cannot inspect path: {candidate}", details={"error": str(exc)}
            ) from exc

        if stat_module.S_ISLNK(info.st_mode):
            raise UnsafePathError(f"Refusing to follow symlink inside run: {candidate}")

    if not is_within(candidate, root_resolved):
        raise UnsafePathError(f"Path escapes the run root: {relative}")
    return candidate


class PathAllocator:
    """Deterministic, case-insensitive filename collision resolution.

    Tracks allocated names per directory (lowercased keys so ``Report.TXT``
    collides with ``report.txt`` on NTFS/APFS) and appends `` (2)``, `` (3)``,
    ... on conflict. Purely lexical — no filesystem probing — so behavior is
    identical on every OS and reproducible for a given seed.
    """

    def __init__(self) -> None:
        self._used: dict[PurePosixPath, set[str]] = {}

    def allocate(self, directory: PurePosixPath, filename: str) -> PurePosixPath:
        """Reserve ``filename`` in ``directory``, suffixing on collision."""
        used = self._used.setdefault(directory, set())
        key = filename.casefold()
        if key not in used:
            used.add(key)
            return directory / filename

        stem, dot, suffix = filename.rpartition(".")
        has_ext = dot and len(suffix) <= 10 and stem
        counter = 2
        while True:
            candidate = f"{stem} ({counter}){dot}{suffix}" if has_ext else f"{filename} ({counter})"
            candidate_key = candidate.casefold()
            if candidate_key not in used:
                used.add(candidate_key)
                return directory / candidate
            counter += 1


def check_path_length(path: Path, *, limit: int = WINDOWS_MAX_PATH - 20) -> list[str]:
    """Return human-readable warnings when a path risks exceeding MAX_PATH."""
    warnings: list[str] = []
    total = len(str(path))
    if total > limit:
        warnings.append(
            f"Path length {total} characters is close to or beyond the classic "
            f"Windows {WINDOWS_MAX_PATH}-character limit; long-path support may be required."
        )
    return warnings

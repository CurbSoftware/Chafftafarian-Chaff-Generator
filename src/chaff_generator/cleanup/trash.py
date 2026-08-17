"""Trash-move support with per-OS failure explanation (spec section 40)."""

from __future__ import annotations

import sys
from pathlib import Path

from chaff_generator.core.errors import CleanupSafetyError

_LINUX_HINT = (
    "On Linux, send2trash needs GIO or a trash-cli backend; headless "
    "servers often have neither. Install 'gio' (glib2) or use --mode delete."
)
_MAC_HINT = "macOS trash access can fail on network or read-only volumes; use --mode delete."
_WINDOWS_HINT = (
    "Windows trash can fail for network drives or when the recycle bin is "
    "disabled by policy; use --mode delete."
)


def explain_trash_failure(exc: Exception) -> str:
    """A plain-language, OS-specific explanation for a failed trash move."""
    if sys.platform.startswith("linux"):
        hint = _LINUX_HINT
    elif sys.platform == "darwin":
        hint = _MAC_HINT
    elif sys.platform == "win32":
        hint = _WINDOWS_HINT
    else:
        hint = "No trash backend is available on this platform; use --mode delete."
    return f"Moving to the trash failed: {exc}. {hint}"


def send_run_to_trash(run_root: Path) -> None:
    """Move the whole run root to the OS trash in a single call (spec section 40).

    Raises :class:`CleanupSafetyError` with the OS-specific explanation when
    no trash backend is available.
    """
    try:
        from send2trash import send2trash
    except ImportError as exc:  # pragma: no cover - send2trash is a hard dep
        raise CleanupSafetyError(explain_trash_failure(exc)) from exc

    try:
        send2trash(str(run_root))
    except Exception as exc:  # send2trash raises various backend errors
        raise CleanupSafetyError(explain_trash_failure(exc)) from exc

"""Safe chaff-run cleanup (spec sections 38-41)."""

from __future__ import annotations

from chaff_generator.cleanup.manager import CleanupManager, CleanupResult
from chaff_generator.cleanup.safety import (
    FORBIDDEN_ROOTS,
    RUN_ID_PATTERN,
    scan_for_symlinks,
    validate_run_root,
)
from chaff_generator.cleanup.trash import explain_trash_failure, send_run_to_trash
from chaff_generator.core.errors import CleanupSafetyError

__all__ = [
    "FORBIDDEN_ROOTS",
    "RUN_ID_PATTERN",
    "CleanupManager",
    "CleanupResult",
    "CleanupSafetyError",
    "explain_trash_failure",
    "scan_for_symlinks",
    "send_run_to_trash",
    "validate_run_root",
]

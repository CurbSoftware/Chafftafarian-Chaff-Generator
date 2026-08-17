"""The cleanup manager: validated, whole-run-root removal (spec sections 38-41).

There is deliberately **no arbitrary-directory delete API** in this module.
The only entry points take a run root that :func:`validate_run_root` has
first proven to be a genuine chaff run, and they always act on the run root
as a whole — never on a hand-picked subpath.
"""

from __future__ import annotations

import os
import shutil
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from chaff_generator.cleanup.safety import scan_for_symlinks, validate_run_root
from chaff_generator.cleanup.trash import send_run_to_trash
from chaff_generator.core.errors import CleanupSafetyError
from chaff_generator.core.models import CompletionAction, GenerationResult, RunStatus

_TRASH_NOTE = (
    "The run is in the Trash/Recycle Bin; storage is not reclaimed until "
    "the operating system's trash is emptied (spec section 40)."
)


@dataclass(frozen=True)
class CleanupResult:
    """What a cleanup pass did."""

    run_root: Path
    mode: CompletionAction
    trashed: bool
    warnings: tuple[str, ...]


class CleanupManager:
    """Removes chaff runs — and nothing else — after paranoid validation."""

    def clean(self, run_root: Path, mode: CompletionAction) -> CleanupResult:
        """Validate ``run_root`` and remove it whole per ``mode``.

        Raises :class:`CleanupSafetyError` when validation fails or removal
        cannot complete. Nothing outside the validated run root is touched.
        """
        if mode is CompletionAction.KEEP:
            raise CleanupSafetyError(
                "Nothing to clean: the completion action is 'keep' "
                "(this is a programming error, not a user mistake)"
            )

        validate_run_root(run_root)
        resolved = run_root.resolve(strict=True)
        warnings = [
            f"note: symlink inside the run removed with it: {link}"
            for link in scan_for_symlinks(resolved)
        ]

        if mode is CompletionAction.TRASH:
            send_run_to_trash(resolved)
            warnings.append(_TRASH_NOTE)
        else:
            self._rmtree(resolved)

        if resolved.exists() or run_root.exists():
            raise CleanupSafetyError(
                f"Cleanup believed it succeeded but {run_root} still exists",
                details={"path": str(resolved), "mode": mode.value},
            )
        return CleanupResult(
            run_root=run_root,
            mode=mode,
            trashed=mode is CompletionAction.TRASH,
            warnings=tuple(warnings),
        )

    def execute_completion_action(
        self, result: GenerationResult, action: CompletionAction
    ) -> CleanupResult | None:
        """Apply the configured completion action to a finished run (§41).

        Destructive actions require the user's explicit selection (they did
        by configuring it) and are never the default. Failed or cancelled
        runs keep their evidence for debugging — this returns ``None``.
        """
        if action is CompletionAction.KEEP:
            return None
        if result.status is not RunStatus.COMPLETED:
            return None
        return self.clean(result.run_root, action)

    def _rmtree(self, resolved: Path) -> None:
        """Remove the tree, clearing read-only bits as needed (Windows)."""
        failures: list[str] = []

        def _on_exc(function: Callable[[str], None], path: str, exc: BaseException) -> None:
            # rmtree fails on read-only files on Windows; clear the bit and
            # retry once before recording the failure.
            try:
                os.chmod(path, stat.S_IWRITE)
                function(path)
            except OSError:
                failures.append(f"{path}: {exc}")

        shutil.rmtree(resolved, onexc=_on_exc)
        if failures:
            raise CleanupSafetyError(
                "Some run contents could not be removed",
                details={"path": str(resolved), "failures": failures},
            )

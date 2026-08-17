"""``chaff clean`` — remove a finished chaff run (spec sections 38-41, 53)."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from chaff_generator.cleanup.manager import CleanupManager
from chaff_generator.cleanup.safety import validate_run_root
from chaff_generator.cli.app import app
from chaff_generator.core.errors import ChaffError, CleanupSafetyError
from chaff_generator.core.models import CompletionAction


class _CleanMode(StrEnum):
    delete = "delete"
    trash = "trash"


@app.command()
def clean(
    run_dir: Annotated[
        Path,
        typer.Argument(
            help="A chaff run directory (Chaff_Run_...). Only validated chaff runs can be cleaned.",
            show_default=False,
        ),
    ],
    mode: Annotated[
        _CleanMode,
        typer.Option(
            "--mode",
            help="'delete' removes permanently; 'trash' moves the run to the OS trash.",
        ),
    ] = _CleanMode.delete,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Skip the confirmation prompt."),
    ] = False,
) -> None:
    """Remove a chaff run after validating it is genuinely one of ours.

    Neighboring files and directories are never touched; a run without a
    valid marker and manifest is refused.
    """
    manager = CleanupManager()
    action = CompletionAction.DELETE if mode is _CleanMode.delete else CompletionAction.TRASH

    # Validate first: a refusal should never depend on whether the user
    # would have confirmed.
    try:
        validate_run_root(run_dir)
    except CleanupSafetyError as exc:
        typer.secho(f"Refusing to clean: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    verb = "permanently delete" if action is CompletionAction.DELETE else "move to the trash"
    if not yes and not typer.confirm(f"{verb.capitalize()} {run_dir}?"):
        typer.echo("Cancelled.")
        return

    try:
        result = manager.clean(run_dir, action)
    except ChaffError as exc:
        typer.secho(f"Cleanup failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    for warning in result.warnings:
        typer.secho(f"Note: {warning}", fg=typer.colors.YELLOW)
    done = "moved to the trash" if result.trashed else "deleted"
    typer.secho(f"Run {done}: {run_dir}", fg=typer.colors.GREEN)

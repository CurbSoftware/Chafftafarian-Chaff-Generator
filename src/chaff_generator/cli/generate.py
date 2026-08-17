"""``chaff generate`` — the command-line generation entry point (§76)."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from chaff_generator.cli.app import app
from chaff_generator.core.engine import ChaffEngine
from chaff_generator.core.errors import ChaffError
from chaff_generator.core.events import ProgressUpdated
from chaff_generator.core.models import (
    CompletionAction,
    FileTypeSetting,
    GenerationConfig,
    LayoutMode,
    TargetMode,
    TargetSpec,
)
from chaff_generator.core.seeding import new_master_seed
from chaff_generator.core.size import format_size, parse_size


class _Layout(StrEnum):
    flat = "flat"
    simple = "simple"
    realistic = "realistic"


class _Completion(StrEnum):
    keep = "keep"
    delete = "delete"
    trash = "trash"


@app.command()
def generate(
    target: Annotated[
        Path,
        typer.Option(
            "--target",
            help="Directory that will hold the run (created if missing).",
            show_default=False,
        ),
    ],
    size: Annotated[
        str | None,
        typer.Option("--size", help="Total volume to generate, e.g. '20 MiB' or '1.5 GB'."),
    ] = None,
    percent_free: Annotated[
        float | None,
        typer.Option(
            "--percent-free",
            min=0.0,
            max=100.0,
            help="Fill this percentage of the currently free space (storage-test mode).",
        ),
    ] = None,
    fill_free_space: Annotated[
        bool,
        typer.Option(
            "--fill-free-space",
            help="Fill the target until only the reserve stays free (storage-test mode).",
        ),
    ] = False,
    reserve: Annotated[
        str,
        typer.Option("--reserve", help="Free bytes to always leave, e.g. '2 GB'."),
    ] = "2 GB",
    profile: Annotated[
        str, typer.Option("--profile", help="Content profile id (see 'chaff packs list').")
    ] = "realistic-desktop",
    types: Annotated[
        str | None,
        typer.Option(
            "--types",
            help="Comma-separated format allowlist (txt,csv,json,...); overrides profile weights.",
        ),
    ] = None,
    layout: Annotated[
        _Layout, typer.Option("--layout", help="Directory layout inside the run.")
    ] = _Layout.realistic,
    seed: Annotated[
        int,
        typer.Option("--seed", help="Master seed (0 = derive a fresh random seed)."),
    ] = 0,
    completion: Annotated[
        _Completion,
        typer.Option("--completion", help="What to do with the run when generation finishes."),
    ] = _Completion.keep,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Load a YAML/JSON preset; CLI flags override it."),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Run preflight checks and exit without writing.")
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", help="Proceed without the large-job confirmation prompt.")
    ] = False,
) -> None:
    """Generate a chaff run into TARGET."""
    try:
        target.mkdir(parents=True, exist_ok=True)
        job_config = _build_config(
            target=target,
            size=size,
            percent_free=percent_free,
            fill_free_space=fill_free_space,
            reserve=reserve,
            profile=profile,
            types=types,
            layout=layout.value,
            completion=completion.value,
            seed=seed,
            config_path=config_path,
        )
    except ChaffError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    engine = ChaffEngine(job_config, event_callback=_make_progress_callback())
    try:
        summary = engine.preflight()
    except ChaffError as exc:
        typer.secho(f"Preflight failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Target      : {summary.target_path}")
    typer.echo(f"Free space  : {format_size(summary.free_bytes)}")
    if summary.requested_bytes is not None:
        typer.echo(
            f"Volume      : {format_size(summary.requested_bytes)} "
            f"(~{summary.estimated_file_count:,} files)"
        )
    typer.echo(f"Profile     : {summary.profile_id}")
    typer.echo(f"Formats     : {', '.join(summary.formats)}")
    typer.echo(f"Seed        : {summary.seed}")
    for warning in summary.warnings:
        typer.secho(f"Warning     : {warning}", fg=typer.colors.YELLOW)

    if dry_run:
        typer.echo("Dry run: nothing written.")
        return

    # Only genuinely consequential jobs (huge file counts) need a prompt;
    # skipped-format notes are informational.
    from chaff_generator.core.engine import FILE_COUNT_WARN_THRESHOLD

    huge_job = summary.estimated_file_count > FILE_COUNT_WARN_THRESHOLD
    if huge_job and not yes and not typer.confirm("Proceed with this job?"):
        typer.echo("Cancelled.")
        raise typer.Exit(code=0)

    try:
        result = engine.generate()
    except ChaffError as exc:
        typer.secho(f"Generation failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("")
    if result.status.value == "completed":
        typer.secho(
            f"Done: {result.files_created:,} files, {format_size(result.bytes_written)} "
            f"in {result.duration_s:.1f}s ({format_size(int(result.throughput_bps))}/s)",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(
            f"Run {result.status.value}: {result.error or 'stopped early'}", fg=typer.colors.YELLOW
        )
    typer.echo(f"Run root  : {result.run_root}")
    if result.manifest_path is not None:
        typer.echo(f"Manifest  : {result.manifest_path}")
    for warning in result.warnings:
        typer.secho(f"Warning   : {warning}", fg=typer.colors.YELLOW)
    typer.echo("Verify with: chaff verify " + str(result.run_root))


def _build_config(
    *,
    target: Path,
    size: str | None,
    percent_free: float | None,
    fill_free_space: bool,
    reserve: str,
    profile: str,
    types: str | None,
    layout: str,
    completion: str,
    seed: int,
    config_path: Path | None,
) -> GenerationConfig:
    if config_path is not None:
        from chaff_generator.core.models import load_config

        base = load_config(config_path)
    else:
        base = GenerationConfig(
            schema_version=1,
            target=TargetSpec(path=target, mode=TargetMode.EXACT, amount=1),
        )

    mode_flags = sum(
        1 for flag in (size is not None, percent_free is not None, fill_free_space) if flag
    )
    if mode_flags != 1:
        raise ChaffError(
            "Give exactly one of --size, --percent-free, or --fill-free-space "
            "(or a preset with target.amount)"
        )

    if size is not None:
        amount = parse_size(size)
        if amount <= 0:
            raise ChaffError(f"Invalid size: {size!r}")
        target_spec = TargetSpec(
            path=target,
            mode=TargetMode.EXACT,
            amount=amount,
            reserve=parse_size(reserve),
        )
    elif percent_free is not None:
        if not 0 < percent_free <= 100:
            raise ChaffError(f"--percent-free must be in (0, 100], got {percent_free}")
        target_spec = TargetSpec(
            path=target,
            mode=TargetMode.PERCENT_FREE,
            percent=Decimal(str(percent_free)),
            reserve=parse_size(reserve),
        )
    else:
        target_spec = TargetSpec(
            path=target,
            mode=TargetMode.FILL_UNTIL_RESERVE,
            reserve=parse_size(reserve),
        )

    file_types: dict[str, FileTypeSetting] = dict(base.file_types)
    if types is not None:
        file_types = {
            fmt.strip(): FileTypeSetting(enabled=True) for fmt in types.split(",") if fmt.strip()
        }
        if not file_types:
            raise ChaffError("--types produced no formats")

    return replace(
        base,
        target=target_spec,
        profile=profile or base.profile,
        seed=seed or new_master_seed(),
        directory_layout=LayoutMode(layout),
        file_types=file_types,
        completion=CompletionAction(completion),
        active_pack=base.active_pack,
    )


def _make_progress_callback():  # type: ignore[no-untyped-def]
    import sys

    def on_event(event: object) -> None:
        if not isinstance(event, ProgressUpdated):
            return
        target = event.target_bytes or 0
        percent = (event.bytes_written * 100 / target) if target else 0.0
        line = f"\r{percent:5.1f}%  {event.files:,} files  {format_size(event.bytes_written)}"
        sys.stdout.write(line)
        sys.stdout.flush()

    return on_event

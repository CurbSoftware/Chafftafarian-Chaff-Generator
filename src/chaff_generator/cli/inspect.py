"""``chaff inspect`` — run metadata at a glance (spec sections 53, 76)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from chaff_generator.cli.app import app
from chaff_generator.core.errors import ChaffError, VerificationError
from chaff_generator.core.size import format_size
from chaff_generator.manifest.models import MANIFEST_FILENAME
from chaff_generator.manifest.reader import (
    discover_runs,
    manifest_for_run,
    read_journal,
)
from chaff_generator.manifest.verifier import (
    VerificationEngine,
    VerificationMode,
)


@app.command()
def inspect(
    run: Annotated[
        Path,
        typer.Argument(
            help="A chaff run directory; or a parent directory to list the runs inside it."
        ),
    ],
) -> None:
    """Show a run's manifest metadata, or list runs under a directory."""
    if (run / MANIFEST_FILENAME).is_file():
        _inspect_run(run)
        return
    if run.is_dir():
        runs = discover_runs(run)
        if not runs:
            typer.secho(f"No chaff runs found under {run}.", fg=typer.colors.YELLOW)
            raise typer.Exit(code=1)
        typer.echo(f"Runs under {run}:")
        for info in runs:
            typer.echo(
                f"  {info.run_id}  {info.created_at}  "
                f"{info.file_count:,} files  {format_size(info.bytes_written)}  "
                f"{info.status}"
            )
        return
    typer.secho(f"Not a chaff run (or directory): {run}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


def _inspect_run(run_root: Path) -> None:
    engine = VerificationEngine()
    try:
        report = engine.verify(run_root, VerificationMode.METADATA)
        manifest = manifest_for_run(report.run_root)
    except (ChaffError, VerificationError) as exc:
        typer.secho(f"Cannot inspect: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(f"Run        : {manifest.run_id}")
    typer.echo(f"Status     : {manifest.status}")
    typer.echo(f"Created    : {manifest.created_at}")
    typer.echo(f"Generator  : {manifest.generator} {manifest.app_version}")
    typer.echo(
        f"Profile    : {manifest.profile or '—'} "
        f"(pack {manifest.pack_id or 'default'} v{manifest.pack_version})"
    )
    typer.echo(f"Seed       : {manifest.seed}")
    typer.echo(
        f"Volume     : {manifest.bytes_written:,} bytes in {len(manifest.files):,} files "
        f"(target {manifest.target_bytes:,})"
    )
    typer.echo(f"Free after : {manifest.free_bytes_after:,} bytes")
    typer.echo(f"Run root   : {report.run_root}")

    journal_path = report.run_root / ".chaff-journal.jsonl"
    journal = read_journal(journal_path)
    typer.echo(f"Journal    : {len(journal)} records in {journal_path.name}")

    typer.echo("")
    counts = report.counts
    typer.echo("Metadata check:")
    for verdict, count in counts.items():
        if count:
            typer.echo(f"  {verdict.value:<13} {count}")
    largest = sorted(manifest.files, key=lambda f: f.size, reverse=True)[:5]
    typer.echo("")
    typer.echo("Largest files:")
    for record in largest:
        typer.echo(f"  {record.size:>12,}  {record.relative_path}")

    typer.echo("")
    typer.echo(f"Verify with: chaff verify {report.run_root}")

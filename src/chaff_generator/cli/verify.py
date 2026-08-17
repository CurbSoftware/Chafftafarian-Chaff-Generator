"""``chaff verify`` and ``chaff inspect`` — integrity commands (spec section 76)."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from chaff_generator.cli.app import app
from chaff_generator.core.errors import ChaffError, VerificationError
from chaff_generator.manifest.reader import read_journal
from chaff_generator.manifest.verifier import VerificationEngine, VerificationMode


class _Mode(StrEnum):
    metadata = "metadata"
    full = "full"
    sample = "sample"


@app.command()
def verify(
    run: Annotated[
        Path,
        typer.Argument(help="Run directory (or its manifest file) to verify."),
    ],
    mode: Annotated[
        _Mode, typer.Option("--mode", help="metadata: sizes only; full: hash everything;")
    ] = _Mode.full,
    sample_percent: Annotated[
        float | None,
        typer.Option("--sample-percent", help="Sample mode: verify this percent of files."),
    ] = None,
    sample_count: Annotated[
        int | None,
        typer.Option("--sample-count", help="Sample mode: verify this many files."),
    ] = None,
    sample_seed: Annotated[
        int, typer.Option("--sample-seed", help="Seed for reproducible sample selection.")
    ] = 0,
    json_out: Annotated[
        Path | None,
        typer.Option("--json", help="Write the full JSON report to this file."),
    ] = None,
    csv_out: Annotated[
        Path | None, typer.Option("--csv", help="Write per-file results as CSV.")
    ] = None,
) -> None:
    """Verify a run's files against its manifest."""
    if mode is _Mode.sample and sample_percent is None and sample_count is None:
        typer.secho(
            "Sample mode needs --sample-percent or --sample-count.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    engine = VerificationEngine()
    try:
        report = engine.verify(
            run,
            VerificationMode(mode),
            sample_percent=sample_percent,
            sample_count=sample_count,
            sample_seed=sample_seed,
        )
    except VerificationError as exc:
        typer.secho(f"Cannot verify: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(report.summary_text())
    if json_out is not None:
        json_out.write_text(report.to_json(), encoding="utf-8")
        typer.echo(f"JSON report : {json_out}")
    if csv_out is not None:
        csv_out.write_text(report.to_csv(), encoding="utf-8")
        typer.echo(f"CSV report  : {csv_out}")

    if report.cancelled:
        raise typer.Exit(code=130)
    if not report.ok:
        raise typer.Exit(code=1)


@app.command()
def inspect(
    run: Annotated[
        Path,
        typer.Argument(help="Run directory (or its manifest file) to inspect."),
    ],
) -> None:
    """Show a run's manifest metadata and a metadata-mode verdict summary."""
    engine = VerificationEngine()
    try:
        report = engine.verify(run, VerificationMode.METADATA)
    except ChaffError as exc:
        typer.secho(f"Cannot inspect: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc

    from chaff_generator.manifest.reader import manifest_for_run

    manifest = manifest_for_run(report.run_root)
    typer.echo(f"Run        : {manifest.run_id}")
    typer.echo(f"Status     : {manifest.status}")
    typer.echo(f"Created    : {manifest.created_at}")
    typer.echo(f"Generator  : {manifest.generator} {manifest.app_version}")
    typer.echo(
        f"Profile    : {manifest.profile} (pack {manifest.pack_id} v{manifest.pack_version})"
    )
    typer.echo(f"Seed       : {manifest.seed}")
    typer.echo(
        f"Volume     : {manifest.bytes_written:,} bytes in {len(manifest.files):,} files "
        f"(target {manifest.target_bytes:,})"
    )
    typer.echo(f"Free after : {manifest.free_bytes_after:,} bytes")

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

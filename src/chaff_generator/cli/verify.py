"""``chaff verify`` — integrity verification (spec section 76)."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from chaff_generator.cli.app import app
from chaff_generator.core.errors import VerificationError
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

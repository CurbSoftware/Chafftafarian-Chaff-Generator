"""``chaff packs`` — ChaffBank pack management (spec sections 50, 53, 76)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from chaff_generator.cli.app import app
from chaff_generator.content.bank import (
    ChaffBank,
    PackManager,
    load_default_pack,
    validate_pack,
)
from chaff_generator.core.errors import ChaffError, PackError

packs_app = typer.Typer(help="List, validate, and import ChaffBank packs.")
app.add_typer(packs_app, name="packs")


@packs_app.command("list")
def list_packs() -> None:
    """Show installed packs (builtin + user packs)."""
    manager = PackManager()
    found = manager.list_packs()
    if not found:
        typer.echo("No packs installed.")
        return
    typer.echo(f"{'Name':24} {'ID':22} {'Ver':8} {'Lang':6} {'Source':8} Location")
    for info in found:
        typer.echo(
            f"{info.manifest.name[:24]:24} {info.manifest.id[:22]:22} "
            f"{info.manifest.version[:8]:8} {info.manifest.language[:6]:6} "
            f"{info.source:8} {info.path}"
        )
    typer.echo(f"\nUser packs install to: {manager.user_packs_dir}")


@packs_app.command("validate")
def validate(
    pack_dir: Annotated[Path, typer.Argument(help="A pack directory to check.")],
) -> None:
    """Validate a pack's structure, banks, and templates."""
    try:
        report = validate_pack(pack_dir)
    except ChaffError as exc:
        typer.secho(f"{exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if report.ok:
        typer.secho("Pack is valid.", fg=typer.colors.GREEN)
    else:
        typer.secho("Pack is invalid:", fg=typer.colors.RED, err=True)
        for error in report.errors:
            typer.echo(f"  error: {error}", err=True)
        raise typer.Exit(code=1)
    for warning in report.warnings:
        typer.secho(f"  warning: {warning}", fg=typer.colors.YELLOW)


@packs_app.command("import")
def import_zip(
    archive: Annotated[Path, typer.Argument(help="Pack ZIP archive to import.")],
    name: Annotated[
        str | None, typer.Option("--name", help="Install under this pack name.")
    ] = None,
) -> None:
    """Import a pack ZIP (zip-slip protected; nothing executable installs)."""
    try:
        info = PackManager().import_zip(archive, dest_name=name)
    except (PackError, ChaffError) as exc:
        typer.secho(f"Import refused: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(
        f"Imported {info.manifest.name} {info.manifest.version} -> {info.path}",
        fg=typer.colors.GREEN,
    )


@packs_app.command("show")
def show(
    pack_dir: Annotated[
        Path | None,
        typer.Argument(help="A pack directory (default: the builtin pack)."),
    ] = None,
) -> None:
    """Summarize a pack's banks and templates."""
    try:
        bank = ChaffBank.load(pack_dir) if pack_dir is not None else load_default_pack()
    except ChaffError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    manifest = bank.manifest
    typer.echo(f"{manifest.name} {manifest.version} ({manifest.id})")
    if manifest.description:
        typer.echo(f"  {manifest.description}")
    typer.echo(f"Templates : {len(bank.templates().all())}")
    typer.echo(f"Profiles  : {', '.join(sorted(bank.profiles()))}")

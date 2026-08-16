"""Root Typer application: the ``chaff`` command.

Subcommands are registered from the sibling modules as they are implemented.
Running ``chaff`` with no subcommand launches the desktop GUI when a display
is available.
"""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from chaff_generator.version import __version__

app = typer.Typer(
    name="chaff",
    help="Chaff Generator — synthetic data corpus generator and integrity verifier.",
    no_args_is_help=False,
    invoke_without_command=True,
    add_completion=False,
)


def _launch_gui() -> None:
    """Import and run the GUI lazily; fail gracefully on headless systems."""
    try:
        from chaff_generator.gui.app import run
    except Exception as exc:  # any Qt import/setup failure counts as headless
        typer.secho(
            f"Cannot start the graphical interface: {exc}\n"
            "No display may be available. Use 'chaff <command> --help' for the "
            "command-line interface.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2) from exc
    raise typer.Exit(code=run())


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: Annotated[
        bool, typer.Option("--version", help="Print the application version and exit.")
    ] = False,
) -> None:
    if version:
        typer.echo(f"chaff-generator {__version__}")
        raise typer.Exit(code=0)
    if ctx.invoked_subcommand is None:
        _launch_gui()


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    sys.exit(app())

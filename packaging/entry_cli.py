"""PyInstaller entry for the CLI (no Qt imported anywhere)."""

from chaff_generator.cli.app import app

if __name__ == "__main__":
    app()

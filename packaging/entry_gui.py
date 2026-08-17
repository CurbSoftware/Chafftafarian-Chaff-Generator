"""PyInstaller entry for the desktop app: import Qt before anything else."""

from chaff_generator.gui.app import run

if __name__ == "__main__":
    raise SystemExit(run())

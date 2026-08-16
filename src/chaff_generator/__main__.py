"""Entry point for ``python -m chaff_generator`` and the ``chaff`` console script."""

from __future__ import annotations


def main() -> None:
    """Run the ``chaff`` command-line application."""
    from chaff_generator.cli.app import app

    app()


if __name__ == "__main__":
    main()

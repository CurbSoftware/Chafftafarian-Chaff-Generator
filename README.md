# Chaff Generator

Chaff Generator creates realistic but entirely synthetic files — documents,
emails, spreadsheets, presentations, exports — and writes a SHA-256 manifest so
the generated corpus can be verified later. It is a deterministic
synthetic-data corpus generator, filesystem capacity tool, and
integrity-verification utility for Windows, Linux, and macOS.

> **Status:** early development (0.1.0). The full workflow documentation lands
> with the first feature-complete release.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

Requires Python 3.12 or newer.

## Use

```bash
chaff                            # GUI
chaff generate --help            # CLI generation
chaff verify --help              # integrity verification
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
mypy
```

Licensed under the MIT License — see [LICENSE](LICENSE).

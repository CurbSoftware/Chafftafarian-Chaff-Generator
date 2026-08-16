# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chaff Generator creates realistic, entirely synthetic files ("chaff") for storage
integrity testing, dummy-dataset generation, and filesystem capacity testing.
It produces coherent collections of genuine everyday file formats from
data-bank-driven templates, writes a SHA-256 manifest for every run, and can
later verify the corpus against that manifest. The authoritative product and
engineering specification is `major-plan.md`.

## Commands

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

pytest                           # full test suite
pytest tests/unit                # one area
ruff check . && ruff format --check .
mypy

chaff --help                     # CLI (generate / verify / clean / inspect / packs)
chaff                            # launch the GUI
```

## Architecture

Layered: the PySide6 GUI (`src/chaff_generator/gui/`) and the Typer CLI
(`src/chaff_generator/cli/`) are thin adapters over the GUI-free core
(`chaff_generator.core.ChaffEngine` and friends). The core never imports Qt;
the CLI never imports Qt unless the GUI is explicitly launched. Public entry:
`from chaff_generator import ChaffEngine`.

Key packages under `src/chaff_generator/`:

- `core/` — engine, planner, config models, events, size parsing, path safety
  (all cross-platform filename/containment rules live in `core/paths.py`),
  seeding (per-file seeds derived from the master seed), hashing, filesystem.
- `content/` — ChaffBank pack loader, the synthetic "generation world", the
  sandboxed Jinja template engine.
- `templates/` + `renderers/` — validated YAML templates produce semantic
  documents; a lazy renderer registry emits txt/md/html/csv/json/xml/eml/
  docx/pdf/xlsx/pptx/vcf/ics/dat files.
- `manifest/` — run marker, journal, manifest, and the verification engine.
- `cleanup/` — safety-validated delete/trash of Chaff run roots only.
- `data/default-pack/` — the built-in ChaffBank (words/phrases/sentences/
  entities/templates/profiles). See its ATTRIBUTION.md for data provenance.

## Hard rules

- Determinism: no process-global `random`; use isolated `random.Random` seeded
  via `core.seeding`. Write text files in binary mode with explicit `\n` so
  hashes match across Windows/Linux/macOS (CRLF only where an RFC requires it:
  .ics/.vcf).
- Safety: never test generation against real/large targets — use `tmp_path`.
  Cleanup must only act on validated Chaff run roots (`.chaff-run.json`).
- No Faker; all content comes from ChaffBank data packs.
- Windows compatibility is a first-class requirement: reserved filenames,
  illegal characters, MAX_PATH, case-insensitive collisions — route through
  `core/paths.py` helpers rather than ad-hoc string handling.

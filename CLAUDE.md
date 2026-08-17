# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository. `AGENTS.md` carries the same rules for any
coding agent — read both; where they overlap, the stricter rule wins.

## Project Overview

Chaff Generator creates realistic but entirely synthetic files (chaff) —
documents, emails, spreadsheets, presentations, exports — records a
SHA-256 manifest as it writes, verifies corpora later, and can safely
remove its own runs. It is a deterministic synthetic-data corpus generator,
filesystem capacity tool, and integrity-verification utility. The
authoritative product spec is `major-plan.md`.

**Cross-platform (Windows, Linux, macOS) is a hard requirement.** The test
suite runs on all three in CI; filesystem behavior differences are exactly
what the safety code exists for.

## Common Commands

```bash
# Setup (Python 3.12+)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Quality gates — run all four before committing
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
mypy src/chaff_generator/
python -m pytest -q

# Run
chaff                                   # GUI (also: python -m chaff_generator)
chaff generate --target <tmpdir> --size "20 MiB" --seed 481925
chaff verify <run-dir>
chaff inspect <run-dir | parent-dir>
chaff clean <run-dir> --mode trash
chaff packs list|show|validate|import
```

Always test generation against a disposable temp directory — never the
real filesystem at scale.

## Architecture

Layered, GUI-free core (details in `docs/architecture.md`):

- `src/chaff_generator/core/` — engine, planner, models, events, seeding,
  hashing, sizing, paths, filesystem capacity. **No Qt, no CLI libs.**
- `content/` — ChaffBank pack loading, synthetic world, sandboxed Jinja
  template engine.
- `templates/`, `renderers/` (lazy registry, one module per format),
  `manifest/` (journal, manifest, verification engine), `cleanup/`
  (paranoid validation + safe delete/trash), `profiles/`.
- `cli/` — Typer commands; **imports no Qt** (headless-safe, §80).
- `gui/` — PySide6 pages/widgets/QThread workers; touches the core only
  through workers so the UI thread never blocks.
- `data/default-pack/` — the built-in ChaffBank pack (banks, entities,
  47 templates, 6 profiles).

Key invariants: core events are frozen dataclasses via a plain callback;
per-file seeds derive from the master seed (no process-global `random`);
same seed ⇒ identical paths/sizes and byte-identical text formats; atomic
`.chaff-partial` → `os.replace` writes; OS-specific logic lives only in
`core/paths.py` and `core/filesystem.py`.

## Safety Rules (spec §38–§41, §72, §79, §87)

- **Never** test Chaff by filling this machine's real filesystem; use
  temp dirs, 1–50 MiB test volumes, mocked free-space probes for fill
  modes; never run free-space-fill benchmarks in CI or casually
  (`scripts/benchmark.py` gates behind `--i-understand-this-writes`).
- Destructive tests only inside disposable temp dirs — never `/`, `C:\`,
  home, `Documents`, `Downloads`, or the repo root.
- Cleanup must never gain an arbitrary-directory delete; it validates run
  identity (marker + manifest + name pattern + protected-root containment)
  before acting, and only on the whole run root.
- Packs are untrusted data: no Python in packs, no eval/exec, sandboxed
  templates, zip-slip-guarded imports.
- Do not weaken the sanitization disclaimer language in README/docs (§79).
- No placeholder code (`pass`/`TODO`/`NotImplementedError`) in completed
  functionality; deferred features are absent, not stubbed
  (see `docs/architecture.md` "Deferred").

## Conventions

- Fully typed public core interfaces; dataclasses over loose dicts; avoid
  `Any` and `# type: ignore`.
- Binary-mode writes with explicit `b"\n"`; CRLF only for `.ics`/`.vcf`
  (RFC 5545/6350); `csv.writer(lineterminator="\n")`.
- pytest markers: `posix_only`, `requires_trash`. GUI tests run offscreen
  (`QT_QPA_PLATFORM=offscreen`, set in `tests/conftest.py` before any Qt
  import).
- Docs live in `docs/` (architecture, chaff-bank, templates,
  integrity-testing, filesystem-safety, development, packaging);
  user-facing changes go in `CHANGELOG.md`.

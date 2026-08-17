# AGENTS.md

Guidance for coding agents (and humans) working in this repository.

## What this project is

Chaff Generator produces realistic, entirely synthetic file corpora
("chaff") with SHA-256 manifests, verifies them later, and can safely
remove them. It runs on Windows, Linux, and macOS — cross-platform
behavior is a hard requirement, not a nicety. The authoritative product
spec is `major-plan.md` (90 sections; §-references below point into it).

## Non-negotiable rules

1. **Never test against a real filesystem at scale** (§72, §87). Automated
   generation tests use `tmp_path`/`tempfile`, stay in the 1–50 MiB range,
   and mock the free-space probe for fill modes. Never run a fill-mode
   benchmark casually; `scripts/benchmark.py` requires an explicit
   `--i-understand-this-writes` flag.
2. **Never point destructive tests at** `/`, `C:\`, home, `Documents`,
   `Downloads`, Desktop, or the repo root. Cleanup tests live in disposable
   temp directories only.
3. **The cleanup API must never gain an arbitrary-directory delete.**
   Deletion requires full run validation (§38–§41). Destructive completion
   actions never default and never run on failed/cancelled runs.
4. **Packs are untrusted data** — no Python in packs, no `eval`/`exec`,
   templates render in the Jinja `SandboxedEnvironment` with
   `StrictUndefined`; ZIP imports are zip-slip-guarded and size-limited.
5. **No placeholder code** — no `pass`/`TODO`/`NotImplementedError` in
   completed functionality. Deferred features (mbox, archives, Corruption
   Lab, resume, charts, marketplace) are absent by design, listed in
   `docs/architecture.md`.
6. **Keep the sanitization disclaimer verbatim** where it appears
   (README, docs) — do not weaken its language (§79).

## Architecture invariants

- `core/ content/ templates/ renderers/ manifest/ cleanup/ profiles/`
  import **no Qt and no CLI libraries**. `from chaff_generator import
  ChaffEngine` must work with no GUI packages installed.
- `cli/` imports no Qt (headless `chaff verify` must not initialize Qt —
  §80). The GUI touches the core only through QThread workers.
- The core publishes frozen-dataclass events through a plain callback —
  never Qt signals.
- Determinism: per-file seeds derive from the master seed; no process-global
  `random` anywhere; dates come from the configured range, never the wall
  clock. Text formats promise byte-identical output for a given seed;
  Office formats promise semantic equality (hash-at-generation is the
  authority).
- OS-specific behavior lives in `core/paths.py` and `core/filesystem.py`
  only: binary-mode writes with explicit `\n` (CRLF only for ics/vcf per
  RFC), `os.replace` atomic renames, close-before-rename, POSIX-only dir
  fsync, `shutil.disk_usage` for capacity.

## Workflow

- Setup: `python3 -m venv .venv && pip install -e ".[dev]"`.
- Gates before any commit (CI runs the same):
  `ruff check src/ tests/ scripts/`, `ruff format --check` on the same,
  `mypy src/chaff_generator/`, `python -m pytest -q`.
- Match the existing style: fully typed public core interfaces, dataclasses
  over loose dicts, no `Any`/`# type: ignore`, comment density like the
  surrounding file.
- GUI tests run offscreen (`QT_QPA_PLATFORM=offscreen`, set in
  `tests/conftest.py`); CLI tests use Typer's `CliRunner`.
- Commits are phase-sized and gate-green. End commit messages with
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## Maps

- Product spec: `major-plan.md` · docs index: `docs/` (architecture,
  chaff-bank, templates, integrity-testing, filesystem-safety, development,
  packaging).
- The built-in pack lives in `src/chaff_generator/data/default-pack/`;
  regenerate nothing there by hand — `scripts/harvest_legacy_data.py`
  documents its provenance.
- The §84 MVP checklist is walked in `docs/mvp-checklist.md`; every bullet
  is covered by an automated test or a documented manual step in
  `docs/development.md`.

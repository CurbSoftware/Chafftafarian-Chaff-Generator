# Development

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Requires Python 3.12+ on Linux, Windows, or macOS.

## Quality gates

Run before every commit (CI runs the same):

```bash
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
mypy src/chaff_generator/
python -m pytest -q
```

GUI tests run headless via `QT_QPA_PLATFORM=offscreen`, which
`tests/conftest.py` sets before any Qt import — no display needed locally
either. The CLI suite never imports Qt at all.

### Test markers

- `posix_only` — POSIX filesystem semantics (symlink escapes, `st_blocks`).
- `requires_trash` — needs an OS trash backend (skipped on headless CI).

### Volume discipline (spec §72/§87)

Never test generation against a real filesystem at scale. Automated tests
use `tmp_path`, keep runs in the 1–50 MiB range, and mock the free-space
probe for fill-mode tests. Destructive cleanup tests live exclusively in
disposable temp directories and never target `/`, `C:\`, home,
`Documents`, `Downloads`, or the repository root. Free-space-fill
benchmarks are never run in CI (`scripts/benchmark.py` demands an explicit
`--i-understand-this-writes` flag for exactly this reason).

## Layout

```text
src/chaff_generator/
├── core/        engine, planner, models, events, paths, filesystem, seeding, hashing, size
├── content/     ChaffBank packs, synthetic world, sandboxed Jinja engine
├── templates/   template models, loader, validation
├── renderers/   one module per output format, lazy registry
├── manifest/    journal, manifest write/read, verification engine
├── cleanup/     paranoid validation + safe delete/trash
├── profiles/    output mix definitions
├── cli/         Typer commands (no Qt)
├── gui/         PySide6 app: pages, widgets, QThread workers
└── data/        the built-in ChaffBank pack
```

Hard rules: the core (`core/ content/ templates/ renderers/ manifest/
cleanup/ profiles/`) imports no Qt and no CLI libraries; the CLI imports no
Qt; the GUI touches the core only through worker threads. No
`# type: ignore`, no `Any` in public core interfaces, no placeholder code —
deferred features (mbox, archives, Corruption Lab, resume) are absent, not
stubbed.

## Manual GUI smoke checklist

Run before releases (5 minutes, against a **disposable** target directory):

```bash
mktemp -d            # use this path as the target everywhere below
chaff                # or: python -m chaff_generator
```

1. **Generate page** — target selector opens a directory picker; an invalid
   target blocks Start; amount field accepts `2 MiB`; free-space label
   updates when the target changes; profile and file-type toggles stick.
2. **Start** — preflight dialog appears with the projected summary; confirm;
   progress panel shows files, throughput, elapsed/ETA; the window stays
   responsive (drag it, switch pages) while generating.
3. **Pause → Resume** — progress parks between files, then continues.
4. **Cancel** — run stops promptly, status is `cancelled`, the run
   directory remains on disk with its journal.
5. **Verify** — a completed run: open Verify page, select the run, full
   mode → summary shows all INTACT; tamper one file outside the app and
   re-verify → HASH_MISMATCH row appears; JSON/CSV export produce files.
6. **Clean** — ResultCard → Delete Chaff on the completed run → run
   directory disappears; place an unrelated `user.txt` beside a fresh run
   and confirm it survives the delete.
7. **ChaffBank page** — template list populates; Preview renders sample
   content with a fixed seed; Validate accepts the built-in pack.
8. **Close mid-run** — start a run and close the window: the app cancels
   and exits within ~5 s without a crash.

## Commit / release flow

Work lands on `main` in phase-sized commits that pass all four gates.
`CHANGELOG.md` records user-visible changes; version lives in
`src/chaff_generator/version.py` and `pyproject.toml`. See
[packaging.md](packaging.md) for building bundles.

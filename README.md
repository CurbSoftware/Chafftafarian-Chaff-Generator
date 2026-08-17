# Chaff Generator

Chaff Generator creates realistic but entirely synthetic files — documents,
emails, spreadsheets, presentations, exports — and writes a SHA-256 manifest
so the generated corpus can be verified later. It is a deterministic
synthetic-data corpus generator, filesystem capacity tool, and
integrity-verification utility for **Windows, Linux, and macOS**.

Every run lands in one self-contained, clearly-marked directory:

```text
Chaff_Run_20260816_203930_f951/
├── .chaff-run.json          # identity marker
├── .chaff-manifest.json     # every file + size + SHA-256
├── .chaff-journal.jsonl     # per-file journal (crash-recoverable)
├── Departments/Finance/2023 Research Notes.txt
├── Documents/…
└── …
```

Nothing is ever scattered into the target directory, and cleanup refuses to
delete anything that is not provably a Chaff run.

## Primary use cases

- **Synthetic chaff / decoy corpora** — fill analysis, de-duplication, DLP,
  and e-discovery pipelines with realistic but fake data instead of real
  files.
- **Storage integrity testing** — generate a known corpus (exact bytes,
  exact hashes), then re-verify after copies, moves, backup/restore cycles,
  or filesystem stress to catch silent corruption.
- **Filesystem capacity testing** — exact amounts (`2 MiB` or `1.5 GB`),
  a percentage of currently free space, or fill-until-reserve, with a
  hard free-space reserve the generator never crosses.
- **Synthetic workstation generation** — profiles that mimic the file mix
  of an office, personal, or developer machine for demos, training, and
  screenshot-safe datasets.

All content is synthetic: identities are assembled from name-frequency
lists, every e-mail address uses reserved non-routable domains
(`example.com`, `*.example`).

## Installation

From source (Python 3.12+):

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

Standalone binaries (no Python required) are built per-OS with PyInstaller —
see [docs/packaging.md](docs/packaging.md). Screenshots will live here once
the project ships a release with them.

## Running the GUI

```bash
chaff                    # or: python -m chaff_generator
```

Five pages: **Generate** (target, amount, reserve, profile, file types,
seed, preflight dialog, live progress with pause/resume/cancel), **Verify**
(metadata/sample/full verification with JSON/CSV export), **Runs**
(history with authoritative manifest data), **ChaffBank** (template pack
browsing, validation, live template preview), and **Settings** (default
target, reserve, completion action).

## Running the CLI

The CLI never initializes Qt — every subcommand works headless:

```bash
chaff generate --target /mnt/scratch/chaff --size "20 MiB" --seed 481925
chaff verify   /mnt/scratch/chaff/Chaff_Run_*        # full hash verification
chaff inspect  /mnt/scratch/chaff                    # list runs / show one
chaff clean    /mnt/scratch/chaff/Chaff_Run_* --mode trash
chaff packs list
```

## Basic generation example

```bash
TMP=$(mktemp -d)
chaff generate --target "$TMP" --size "20 MiB" --seed 481925
```

```text
Done: 11 files, 20 MiB in 4.9s (4.1 MiB/s)
Run root  : /tmp/tmp.SiPJWXsRfY/Chaff_Run_20260816_204610_f951
Verify with: chaff verify /tmp/tmp.SiPJWXsRfY/Chaff_Run_20260816_204610_f951
```

Useful `generate` options: `--size "1.5 GB"` (exact) · `--percent-free 40`
· `--fill-free-space` · `--reserve "2 GB"` · `--profile developer-workstation`
· `--types txt,csv,json` · `--layout flat|simple|realistic` ·
`--completion keep|delete|trash`. Same seed ⇒ same relative paths, sizes,
and (for text formats) byte-identical content.

## Integrity verification

```bash
chaff verify <run-dir>                       # hash every file (INTACT/MISSING/…)
chaff verify <run-dir> --mode metadata       # existence + size, instant
chaff verify <run-dir> --mode sample --sample-percent 5
chaff verify <run-dir> --json report.json --csv report.csv
```

Full verification detects a **changed** file (`HASH_MISMATCH`) and a
**deleted** file (`MISSING`) by comparing disk against the run's SHA-256
manifest. Details: [docs/integrity-testing.md](docs/integrity-testing.md).

## Template packs

Content comes from data-only **ChaffBank packs** — word banks, sentence
pools, entity lists, Jinja document templates, and generation profiles. The
built-in English pack ships inside the app; import your own as a ZIP:

```bash
chaff packs import my-pack.zip
chaff packs validate ~/.local/share/chaff-generator/packs/my-pack
```

Guides: [docs/chaff-bank.md](docs/chaff-bank.md) ·
[docs/templates.md](docs/templates.md).

## Important storage / sanitization disclaimer

Chaff Generator creates and deletes ordinary filesystem files. Free-Space
Fill may be useful for storage testing and overwriting currently
addressable free filesystem space, but it is not a substitute for
device-appropriate sanitization, cryptographic erase, secure erase, or
physical destruction where those methods are required.

## Development

```bash
pip install -e ".[dev]"
ruff check src/ tests/ scripts/ && mypy src/chaff_generator/ && python -m pytest -q
```

Architecture, safety model, and the manual GUI smoke checklist:
[docs/architecture.md](docs/architecture.md) ·
[docs/filesystem-safety.md](docs/filesystem-safety.md) ·
[docs/development.md](docs/development.md). MIT licensed.

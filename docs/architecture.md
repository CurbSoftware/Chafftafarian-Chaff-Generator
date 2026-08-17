# Architecture

Chaff Generator is a layered desktop application with a GUI-free core.

```text
┌────────────────────────────┐  ┌───────────────────────────┐
│  PySide6 GUI (gui/)        │  │  Typer CLI (cli/)         │
│  pages · widgets · workers │  │  chaff generate|verify|…  │
└──────────────┬─────────────┘  └──────────────┬────────────┘
               │        both are thin adapters │
               ▼                               ▼
        ┌─────────────────────────────────────────────┐
        │  chaff_generator core (no Qt, no CLI libs)  │
        │  ChaffEngine · Planner · Renderers          │
        │  Content (ChaffBank, world, templates)      │
        │  Manifest · Verifier · Cleanup · Profiles   │
        └─────────────────────────────────────────────┘
```

`from chaff_generator import ChaffEngine` works with no GUI packages
installed; the CLI never imports Qt, and the GUI imports the core only
through workers.

## Major components

| Package | Responsibility |
| --- | --- |
| `core/` | Engine lifecycle, planning, models, events, sizing, paths, filesystem capacity, seeding, hashing |
| `content/` | ChaffBank loading, synthetic world construction, entity generators, the sandboxed Jinja engine |
| `templates/` | Template definitions, loader, validation |
| `renderers/` | One module per output format behind a lazy registry |
| `manifest/` | Run marker, journal, manifest write/read, verification engine |
| `cleanup/` | Paranoid run validation and safe delete/trash |
| `profiles/` | Content profiles (format weights, size distributions) |
| `cli/`, `gui/` | Thin frontends; no business logic |

## Run lifecycle

1. **Preflight** (`ChaffEngine.preflight`) — target writability probe,
   free-space check against the reserve, renderer availability, file-count
   estimate. Produces the summary shown in the §44 dialog / CLI table.
2. **Run root** — `Chaff_Run_YYYYMMDD_HHMMSS_<4hex>` under the target,
   stamped with `.chaff-run.json` (the identity marker cleanup requires).
3. **World + plan** — the master seed builds one immutable synthetic world
   (people, org, projects, timeline). The planner draws per-file seeds
   (`sha256("chaff-file-seed:v1:{master}:{index}")`), formats, sizes, and
   paths from that world.
4. **Render loop** — per file: semantic document → renderer →
   `.chaff-partial` stream → hash-while-writing → atomic `os.replace` →
   journal append → event. Cancellation is checked between files and inside
   streaming chunks; pause parks between files.
5. **Manifest** — `.chaff-manifest.json` records every file with size and
   SHA-256, plus run identity, seed, profile, versions, and status.
6. **Verify** (`manifest/verifier`) — re-reads files and compares against
   the manifest: metadata, sample, or full-hash modes.
7. **Cleanup** (`cleanup/`) — validates the run root (marker, manifest,
   name pattern, protected locations) before any removal; delete or a
   single trash call for the whole run root.

## Event flow

The engine publishes frozen dataclass events through a plain callback
(`core/events.py`) — no Qt anywhere in the core. The CLI adapts them to a
rate-limited terminal line; the GUI's `GenerationWorker` re-emits them
through Qt signals, which auto-queue onto the UI thread.

## Determinism

Given the same seed, pack, and config: the same relative paths, sizes, and
— for text-based formats — byte-identical file contents. Office formats
(zip archives with internal timestamps) promise semantic equality; the
hash recorded at generation time is the authoritative integrity reference.

## Journal durability policy

`.chaff-journal.jsonl` is appended and flushed per record and fsynced
periodically, so an interrupted run leaves a replayable record of every
completed file even without a final manifest.

## Deferred (documented, no stubs)

Mbox/Maildir output, archive formats (zip/tar), the Corruption Lab, run
resume, charts in presentations, and any pack marketplace are future work.
The journal and per-file identity model exist to support them.

# Changelog

All notable changes to Chaff Generator. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[SemVer](https://semver.org/).

## [0.1.0] — 2026-08-16

First feature-complete release (MVP per the project plan).

### Added

- **Generation core** — deterministic, seeded corpus generation into a
  single owned `Chaff_Run_*` directory per run; exact-amount, percentage-of
  -free, and fill-until-reserve target modes; continuous filesystem
  free-space monitoring with a hard reserve; pause/resume/cancel honored
  between files and inside streaming chunks; crash-recoverable per-file
  journal; atomic `.chaff-partial` → `os.replace` writes.
- **Formats** — txt, log, md, html, csv, json, xml, eml (threaded, with
  attachments), docx, pdf, xlsx, pptx, vcf, ics, `.dat` storage payload,
  and developer-style files; every format hashed with SHA-256 while it
  streams to disk.
- **Content** — data-only ChaffBank packs: word/phrase/sentence banks,
  entity data (US-Census-derived name frequencies), 47 validated document
  templates rendered in a locked-down Jinja sandbox, and 6 generation
  profiles (`realistic-desktop`, `office-workstation`, `personal-computer`,
  `developer-workstation`, `balanced`, `storage-test`).
- **Integrity verification** — metadata, sample (seeded), and full-hash
  modes with `INTACT`/`MISSING`/`SIZE_MISMATCH`/`HASH_MISMATCH`/`UNREADABLE`
  verdicts, JSON/CSV reports, and stable exit codes.
- **Safe cleanup** — paranoid run validation (marker, manifest identity,
  name pattern, protected-root containment) before delete or a single-call
  trash; no arbitrary-directory deletion API exists; failure/cancelled runs
  are kept for inspection.
- **GUI** (PySide6) — Generate (with preflight dialog and live progress),
  Verify, Runs history, ChaffBank pack browsing/preview, Settings; all core
  work on QThread workers so the UI stays responsive.
- **CLI** (Typer, Qt-free) — `chaff generate | verify | inspect | clean |
  packs`, plus `python -m chaff_generator` / bare `chaff` launching the GUI.
- **Packaging & CI** — PyInstaller specs + `scripts/build.py` with
  post-build smoke checks for CLI and GUI bundles; CI on Linux, Windows,
  and macOS (lint, types, tests; bundle builds on manual dispatch;
  free-space-fill benchmarks never run in CI).

### Safety

- Never scatters files into the target; never writes outside the run root;
  never symlinks; reserve never crossed even with concurrent disk writers.
- Full sanitization disclaimer and filesystem safety model documented in
  `README.md` and `docs/filesystem-safety.md`.

## [Unreleased]

Legacy prototype history (pre-rewrite) is preserved in git history.

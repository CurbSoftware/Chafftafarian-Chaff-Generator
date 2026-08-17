# MVP Completion Checklist (spec §84)

Every §84 criterion, each backed by an automated test (run in CI on Linux,
Windows, and macOS) or a documented manual step from
[development.md](development.md). Test ids are `pytest` node ids — run any
of them with
`python -m pytest "<node id>"`.

| # | Criterion | Evidence |
| --- | --- | --- |
| 1 | GUI starts successfully | `tests/ui/test_gui.py::TestAppShell::test_main_window_launches` (offscreen); manual step 0 |
| 2 | CLI works without GUI | CLI suites (`tests/integration/test_cli_commands.py`, `…::TestCli`) never import Qt; `packaging/chaff-cli.spec` excludes PySide6 and `scripts/build.py` smoke-checks the Qt-free bundle |
| 3 | User can select a target | `TestGenerateForm::test_invalid_target_blocks_config`; `TestLifecycle::test_preflight_catches_missing_target`; manual step 1 |
| 4 | User can specify amount | `TestAmountField::test_parses_sizes` / `test_rejects_garbage_with_message`; `test_exact_config_shape`, `test_percent_config_shape`, `test_fill_config_shape` |
| 5 | User can specify free-space reserve | `tests/unit/test_filesystem.py::TestFreeSpaceMonitor` (reserve violation, enforcement); `TestFillModes::test_exact_mode_never_crosses_reserve` |
| 6 | User can select file types | `TestGenerateForm::test_type_checkboxes_restrict_formats`; planner weights in `tests/unit/test_planner.py` |
| 7 | User can select a profile | `tests/unit/test_profiles.py` (all six resolve); profile lands in configs (`test_exact_config_shape`) |
| 8 | User can enter/reuse a seed | `TestDeterminism::test_same_seed_same_plan_and_content` / `test_different_seed_different_plan`; `tests/unit/test_seeding.py` |
| 9 | Chaff creates a unique owned run directory | `TestFullRun::test_run_root_and_marker` (name pattern + `.chaff-run.json` identity) |
| 10 | Chaff creates coherent synthetic content | `tests/unit/test_world.py` (12 tests: org coherence, reserved e-mail domains, §64 chronology); `tests/unit/test_template_engine.py` |
| 11 | TXT generation works | `TestExactSizeContract::test_txt_lands_exactly[16/512/4096/90000]`; `test_txt_multibyte_boundary_cut_is_valid_utf8` |
| 12 | EML generation works | `TestEngineRichFormats::test_single_format_run_completes[eml]`; `TestEml::test_parses_with_required_headers`, `test_attachment_decodes`, `test_threading_headers_coherent` |
| 13 | DOCX generation works | `…[docx]`; `TestDocx::test_reopens_with_python_docx` |
| 14 | PDF generation works | `…[pdf]`; `TestPdf::test_header_eof_structure` |
| 15 | XLSX generation works | `…[xlsx]`; `TestXlsx::test_reopens_with_openpyxl`, `test_currency_and_date_cells_typed` |
| 16 | PPTX generation works | `…[pptx]`; `TestPptx::test_reopens_with_python_pptx` |
| 17 | JSON/CSV/HTML/Markdown generation works | `TestParserValidity::test_csv_parses`, `test_json_parses`, `test_html_is_well_formed`, `test_md_structure` (+ xml, log, devfile) |
| 18 | Genuine files are produced | `TestFullRun::test_twenty_mib_run_matches_manifest` (real 20 MiB run); each Office file re-opens with its native library |
| 19 | SHA-256 hashes are recorded | `test_twenty_mib_run_matches_manifest` (manifest hashes match re-hashed disk); `tests/unit/test_hashing.py`; `tests/unit/test_manifest.py` |
| 20 | Final manifest is generated | `TestFullRun::test_run_root_and_marker`; manifest/journal round-trip in `tests/unit/test_manifest.py` |
| 21 | Full verification detects a changed file | `TestSection75Critical::test_tamper_and_delete_are_caught` (HASH_MISMATCH); `test_size_change_is_caught_before_hashing` |
| 22 | Verification detects a deleted file | `TestSection75Critical::test_tamper_and_delete_are_caught` (MISSING); `TestHostileManifests::test_symlink_replacement_is_missing` |
| 23 | Cleanup cannot delete unrelated files | `TestValidateRunRoot::test_refuses_*` (9 refusals incl. forbidden roots, `/`, home, symlinked root); `TestCleanupManagerDelete::test_delete_run_with_unrelated_nested_content`; `TestFullRun::test_unrelated_files_survive` |
| 24 | Delete works on a validated Chaff run | `TestCleanupManagerDelete::test_delete_removes_run_and_only_the_run`; `TestCompletionActionWiring::test_delete_after_completed_run` |
| 25 | Trash works where supported | `TestCleanupManagerTrash::test_trash_moves_whole_root_in_single_call` (`requires_trash`); `test_explanation_names_the_platform` for unsupported hosts |
| 26 | Cancellation works | `TestLifecycle::test_cancel_stops_early_but_keeps_evidence`; GUI: `TestGenerationFlow::test_cancel_mid_run_keeps_evidence`; manual step 4 |
| 27 | Disk-full errors are handled safely | `TestFillModes::test_foreign_writer_stops_run_at_reserve` (concurrent writer → graceful stop at reserve, run COMPLETED with warnings, journal intact); `test_fill_until_reserve_stops_at_reserve` |
| 28 | UI remains responsive while generating | Generation runs on a `QThread` worker (`tests/ui/test_gui.py::TestGenerationFlow::test_full_run_via_gui` drives a real run through the worker); manual step 2 (drag window mid-run) |
| 29 | Automated tests pass | 327 tests green via the four quality gates; CI matrix ubuntu/windows/macos (`.github/workflows/ci.yml`) |
| 30 | Documentation describes all major workflows | This `docs/` set: architecture, chaff-bank, templates, integrity-testing, filesystem-safety, development, packaging + `README.md` |

## Manual steps referenced above

From the manual GUI smoke checklist in [development.md](development.md):

- **Step 0** — `chaff` launches the GUI window.
- **Step 1** — target picker works; invalid target blocks Start; amount,
  reserve, profile, and type toggles all take effect (preflight reflects
  them).
- **Step 2** — during a run the window can be dragged and pages switched.
- **Step 4** — Cancel stops the run promptly; status `cancelled`; evidence
  preserved.

Steps 3 (pause/resume), 5 (verify + tamper), 6 (clean with neighbor
survival), 7 (ChaffBank preview), and 8 (close mid-run) are additionally
covered by automated equivalents: `TestLifecycle::test_pause_resume_completes`,
`TestVerifyFlow::test_verify_via_gui`,
`TestResultCardSafety::test_delete_refuses_tampered_run`, and the
`closeEvent` cancel-and-wait path exercised by worker teardown in the UI
suite.

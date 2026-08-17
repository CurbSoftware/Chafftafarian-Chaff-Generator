# Integrity Testing

Chaff Generator's second job, after making files, is *proving they are
still the files it made*. The loop is:

```text
generate → manifest → verify
```

## Generate

Every run lives in its own owned directory:

```text
Chaff_Run_20260816_203930_f951/
├── .chaff-run.json          # identity marker (run_id, timestamps)
├── .chaff-manifest.json     # final manifest: every file + SHA-256
├── .chaff-journal.jsonl     # per-file journal, flushed as files land
├── Documents/…
├── Departments/Finance/…
└── …
```

As each file is written it is hashed **while it streams to disk** (the digest
and the bytes come from the same pass — nothing is re-read), the write lands
via an atomic `os.replace` from a `.chaff-partial` sibling, and a journal
record is appended and flushed. An interrupted run (crash, power loss,
cancel) therefore leaves a replayable record of every file that completed,
even when no final manifest exists.

## Manifest

`.chaff-manifest.json` records, per file: relative path, size in bytes, and
SHA-256 digest — plus run identity (`run_id`), the master seed, profile,
pack id/version, app version, target byte amount, free space after the run,
and the run status (`completed` / `failed` / `cancelled`).

The manifest is the authority. Verification never trusts the journal for
correctness (the journal is crash-recovery data); it compares the disk
against the manifest.

## Verify

```bash
chaff verify <run-dir>                      # full: hash every file
chaff verify <run-dir> --mode metadata      # existence + size only (fast)
chaff verify <run-dir> --mode sample --sample-percent 5
chaff verify <run-dir> --mode sample --sample-count 25
chaff verify <run-dir> --json report.json --csv report.csv
```

Each file receives a verdict:

| Verdict | Meaning |
| --- | --- |
| `INTACT` | Size and SHA-256 match the manifest |
| `MISSING` | The file is gone |
| `SIZE_MISMATCH` | Present, but the byte count differs |
| `HASH_MISMATCH` | Present, right size, **different content** |
| `UNREADABLE` | Present but could not be read (permissions, I/O error) |

Exit codes: `0` all intact · `1` integrity failures found · `2` the run
itself could not be read · `130` verification was cancelled. Sample
selection is seeded (`--sample-seed`, default 0) so the same sample can be
re-verified reproducibly.

## The canonical tamper demo

```bash
TMP=$(mktemp -d)
chaff generate --target "$TMP" --size "20 MiB" --seed 481925 --yes
RUN=$(ls -d "$TMP"/Chaff_Run_*)
chaff verify "$RUN"                     # Verification: OK … all INTACT

# change one file's contents, delete another
echo tampered >> "$(find "$RUN" -type f -name '*.txt' | head -1)"
find "$RUN" -type f -name '*.txt' | sed -n 2p | xargs rm
chaff verify "$RUN"                     # 1 HASH_MISMATCH, 1 MISSING
```

This exact sequence (including proving an unrelated `user.txt` next to the
run survives cleanup) is automated in
`tests/safety/test_cleanup.py` and `tests/integration/test_verification.py`
and runs in CI on Linux, Windows, and macOS.

## When verification matters

- **After copying or moving a run** — transport can corrupt; metadata mode
  finds truncation instantly, full mode finds bit flips.
- **Before cleanup** — `chaff clean` validates run identity, not content;
  run a full verify first when the run's evidence matters.
- **Storage-test workflows** — `storage-test` profile runs write
  deterministic payload files precisely so a later full verify distinguishes
  real corruption from normal filesystem behavior.

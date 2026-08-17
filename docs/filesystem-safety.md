# Filesystem Safety

Chaff Generator writes large amounts of data and deletes run directories.
Both operations are fenced by design. This page documents the fences.

## Containment — where writes may land

- **Never scatter.** A run always creates one new, uniquely named child
  directory under the target: `Chaff_Run_YYYYMMDD_HHMMSS_<4hex>`. Every file
  the run writes lives inside it. Existing files in the target are never
  touched, appended to, or overwritten.
- **Atomic writes.** Each file is written to a `.chaff-partial` sibling,
  closed, hashed, then moved into place with `os.replace`. Readers never see
  a half-written file, and a crash leaves at worst a `.chaff-partial` inside
  the run root — never a corrupt final file.
- **Path safety.** Generated relative paths are sanitized on every OS:
  Windows-reserved names (`CON`, `PRN`, `COM1`…), illegal characters,
  trailing dots/spaces, and `..` are rejected or rewritten; path length is
  managed; the case-insensitive path allocator avoids NTFS/APFS collisions.
  Filenames are made safe **on all platforms** because chaff files migrate
  between machines.
- **No symlinks, ever.** The generator does not create them, and path joins
  walk parents so a symlinked directory cannot redirect a write outside the
  run root.
- **Reserve enforcement.** The disk reserve (`--reserve`, default 1 GiB) is
  checked continuously during generation, and the filesystem — not the
  byte counter — is the source of truth: free space is re-polled while
  streaming, so concurrent writers (or another program filling the disk)
  cannot push the volume past the reserve. Fill modes stop at the reserve,
  even mid-file.
- **No block devices, no escalation.** Chaff works on ordinary directories
  through ordinary file APIs. It never opens raw devices and never asks for
  elevated privileges.

## Cleanup — what deletion requires

`chaff clean` (and the GUI's Delete/Trash actions) refuse to remove a
directory unless **all** of these hold:

1. The basename matches `Chaff_Run_\d{8}_\d{6}_[0-9a-f]{4}` exactly.
2. `.chaff-run.json` exists, parses, contains `chaff_run: true`, and its
   `run_id` equals the directory's own name.
3. The manifest (if present) agrees on the run's identity.
4. The resolved run root is not itself a symlink, and no symlink required to
   reach it redirects elsewhere.
5. The deletion target is not — and does not contain — a protected root:
   `/`, `C:\`, the user's home, `Documents`, `Downloads`, `Desktop`
   (Windows-style roots are enforced where they exist).

A run *inside* a protected parent (e.g. a run under `~/Downloads/staging/`)
is fine — only runs that would take the protected location with them are
refused. Refusal lists every reason and exits non-zero; it never depends on
a confirmation answer — validation happens **before** the prompt.

When validation passes, deletion acts on the **whole run root only**, via
`shutil.rmtree` (with a read-only-bit retry for Windows) or a **single**
`send2trash(run_root)` call for trash mode. There is no API anywhere in the
codebase that deletes an arbitrary user-chosen directory. Failure and
cancellation keep the run directory intact for inspection — destructive
completion actions only ever run against runs whose status is `completed`,
and "delete" is never the default completion action.

Neighbor safety is enforced by tests: files and folders sitting *beside*,
*above*, and *below* a run directory survive every cleanup path, and a run
whose files were tampered with is still cleaned (it is ours) while an
unrelated directory wearing a similar name is not.

## Capacity — what generation may consume

- Exact (`--size`), percent-of-free (`--percent-free`), and fill-until-
  reserve (`--fill-free-space`) modes share one planner that never crosses
  the reserve and never lets the logical byte count outrun the filesystem.
- Disk-full and permission errors during a single file fail that file,
  warn, and continue; a run-level failure ends the run gracefully with
  status `failed` and the journal preserved.
- Cancellation is honored between files and inside streaming chunks.

## Testing discipline

The test suite treats the host machine as hostile territory: generation
tests use `pytest` temp directories with small volumes, fill-mode tests mock
the free-space probe, and destructive cleanup tests run only inside
disposable temp directories. Nothing in the suite or CI fills a real
filesystem (spec §72/§82/§87).

## Sanitization disclaimer

> Chaff Generator creates and deletes ordinary filesystem files. Free-Space
> Fill may be useful for storage testing and overwriting currently
> addressable free filesystem space, but it is not a substitute for
> device-appropriate sanitization, cryptographic erase, secure erase, or
> physical destruction where those methods are required.

# Packaging

Chaff Generator ships as standalone binaries built with PyInstaller — end
users need no Python, no Microsoft Office, and no LibreOffice; every
supported format is written directly by bundled libraries.

## Artifacts

| Flavor | Spec | Result |
| --- | --- | --- |
| CLI | `packaging/chaff-cli.spec` | single-file console binary (`chaff` / `chaff.exe`) |
| GUI | `packaging/chaff-gui.spec` | `ChaffGenerator/` folder bundle (windowed) |

The CLI bundle **excludes PySide6 entirely** — `chaff verify …` works on a
headless Linux box with no Qt present. The GUI bundle collects all GUI
submodules explicitly.

Both bundles embed:

- the **built-in ChaffBank pack** (`chaff_generator/data`, via `datas`) —
  word banks, sentences, entities, templates, profiles;
- **every renderer module** — renderers are imported lazily through a
  string registry, so PyInstaller's static analysis cannot see them; the
  specs list all of them in `hiddenimports` explicitly.

## Building

On each target OS (build on the OS you ship for — PyInstaller does not
cross-compile):

```bash
pip install -e ".[dev]"

python scripts/build.py --cli    # build + smoke-check the CLI bundle
python scripts/build.py --gui    # build + smoke-check the GUI bundle
```

`scripts/build.py` runs PyInstaller against the matching spec and then
**smoke-checks the artifact**: `--version`, then a real generate → verify →
clean cycle of a 2 MiB run inside a disposable temp directory. A bundle
that cannot round-trip its own output fails the build.

Artifacts land in `dist/` (CLI) and `dist/ChaffGenerator/` (GUI).

## CI builds

`.github/workflows/ci.yml` has a manual (`workflow_dispatch`) **bundles**
job that builds both flavors on ubuntu/windows/macos runners and uploads
them as artifacts. It never runs free-space-fill benchmarks (spec §82).

## Signing and notarization

Code signing (Windows Authenticode, macOS notarization) is **out of scope**
for this repository: it requires certificates and accounts only the
releasing party holds. When distributing binaries, sign/notarize with your
own credentials after `scripts/build.py` succeeds.

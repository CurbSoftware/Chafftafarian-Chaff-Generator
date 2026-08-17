#!/usr/bin/env python3
"""Build standalone Chaff Generator bundles with PyInstaller (spec section 81).

Detects the host OS, builds the matching artifact(s), then smoke-checks the
result by running the bundled CLI's --version and a tiny generation round
trip inside a temporary directory. Usage:

    python scripts/build.py            # build whatever this OS supports
    python scripts/build.py --cli      # CLI only
    python scripts/build.py --gui      # GUI only
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST = PROJECT_ROOT / "dist"


def run_step(title: str, command: list[str]) -> None:
    print(f"==> {title}")
    started = time.monotonic()
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    print(f"    done in {time.monotonic() - started:.0f}s")


def build(flavor: str) -> Path:
    spec = PROJECT_ROOT / "packaging" / f"chaff-{flavor}.spec"
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", str(spec)]
    run_step(f"PyInstaller {flavor}", command)
    if flavor == "cli":
        executable = DIST / ("chaff.exe" if sys.platform == "win32" else "chaff")
    else:
        folder = DIST / "ChaffGenerator"
        name = "ChaffGenerator.exe" if sys.platform == "win32" else "ChaffGenerator"
        executable = folder / name
    if not executable.exists():
        raise SystemExit(f"build produced no artifact at {executable}")
    return executable


def smoke_check(executable: Path) -> None:
    """--version plus a real tiny generate/verify round trip (spec section 72:
    megabytes, inside a temp dir, never the host filesystem at scale)."""
    run_step("version check", [str(executable), "--version"])
    with tempfile.TemporaryDirectory(prefix="chaff-build-smoke-") as tmp:
        target = Path(tmp) / "runs"
        target.mkdir()
        run_step(
            "smoke generate",
            [
                str(executable),
                "generate",
                "--target",
                str(target),
                "--size",
                "2 MiB",
                "--seed",
                "481925",
            ],
        )
        run_root = next(path for path in target.iterdir() if path.is_dir())
        run_step("smoke verify", [str(executable), "verify", str(run_root)])
        run_step("smoke clean", [str(executable), "clean", str(run_root), "--yes"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", action="store_true", help="Build the CLI bundle only.")
    parser.add_argument("--gui", action="store_true", help="Build the GUI bundle only.")
    args = parser.parse_args()

    flavors: list[str] = []
    if args.cli:
        flavors.append("cli")
    if args.gui:
        flavors.append("gui")
    if not flavors:
        flavors = ["cli", "gui"]

    print(f"platform: {sys.platform}")
    for flavor in flavors:
        executable = build(flavor)
        if flavor == "cli":
            smoke_check(executable)
        else:
            print(f"==> gui artifact at {executable} (launch smoke is manual)")
    print("build OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

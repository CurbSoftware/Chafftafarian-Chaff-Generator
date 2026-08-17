#!/usr/bin/env python3
"""Throughput benchmark for Chaff Generator (spec section 72).

This script writes REAL data at scale onto a filesystem you name. It exists
for manual measurements only and never runs in CI or tests. It refuses to
do anything without ``--i-understand-this-writes``.

Example:
    python scripts/benchmark.py --target /mnt/test-disk/bench --size 10 GiB
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow running straight from a source checkout without installing.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chaff_generator import ChaffEngine
from chaff_generator.core.models import (
    FileTypeSetting,
    GenerationConfig,
    LayoutMode,
    TargetMode,
    TargetSpec,
)
from chaff_generator.core.size import format_size, parse_size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True, help="Directory to fill.")
    parser.add_argument("--size", default="1 GiB", help="Volume to generate (default 1 GiB).")
    parser.add_argument("--seed", type=int, default=481_925, help="Master seed.")
    parser.add_argument(
        "--payload", action="store_true", help="Use the storage-test profile (payload-heavy)."
    )
    parser.add_argument(
        "--i-understand-this-writes",
        action="store_true",
        help="Confirmation that real data will be written at scale to TARGET.",
    )
    args = parser.parse_args()

    if not args.i_understand_this_writes:
        parser.error(
            "refusing to run: this benchmark writes real data at scale; pass "
            "--i-understand-this-writes and point --target at a scratch disk"
        )
    if args.target.resolve() == Path("/"):
        parser.error("refusing to write to the filesystem root")

    amount = parse_size(args.size)
    args.target.mkdir(parents=True, exist_ok=True)
    profile = "storage-test" if args.payload else "realistic-desktop"
    config = GenerationConfig(
        schema_version=1,
        target=TargetSpec(path=args.target, mode=TargetMode.EXACT, amount=amount),
        seed=args.seed,
        directory_layout=LayoutMode.SIMPLE,
        profile=profile,
        file_types={
            "dat": FileTypeSetting(enabled=True),
            "txt": FileTypeSetting(enabled=True),
            "log": FileTypeSetting(enabled=True),
        }
        if args.payload
        else {},
    )

    engine = ChaffEngine(config)
    summary = engine.preflight()
    print(f"target={summary.target_path} free={format_size(summary.free_bytes)}")
    started = time.monotonic()
    result = engine.generate()
    elapsed = time.monotonic() - started

    print(f"status={result.status.value} files={result.files_created:,}")
    print(f"bytes={result.bytes_written:,} ({format_size(result.bytes_written)})")
    print(f"wall={elapsed:.2f}s throughput={result.bytes_written / elapsed / 2**20:.1f} MiB/s")
    print(f"run_root={result.run_root}")
    print(f"verify: chaff verify {result.run_root}")
    return 0 if result.status.value == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

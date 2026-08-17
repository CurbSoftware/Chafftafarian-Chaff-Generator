"""Phase 5 storage-mode tests: payload renderer, fill modes, monitoring.

Fill-until-reserve behavior is tested against a **virtual disk** (spec
section 72): ``free_bytes`` is monkeypatched so runs see a small fake
capacity instead of the host filesystem. Real writes stay a few MiB inside
``tmp_path``.
"""

from __future__ import annotations

import hashlib
import random
import subprocess
import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from chaff_generator import ChaffEngine
from chaff_generator.content.bank import load_default_pack
from chaff_generator.content.context import RenderContext
from chaff_generator.content.template_engine import ChaffTemplateEngine
from chaff_generator.content.world import build_world
from chaff_generator.core.events import FileCompleted
from chaff_generator.core.models import (
    FileTypeSetting,
    RunStatus,
    TargetMode,
    TargetSpec,
)
from chaff_generator.renderers import build_registry
from chaff_generator.renderers.payload import CHUNK_BYTES, _chunk

MIB = 1 << 20


class FakeDisk:
    """Virtual free-space oracle.

    Reports ``capacity - bytes-on-disk-under-root - foreign_debit``. The
    run's own files count (the model mirrors reality), and tests can grow
    ``foreign_debit`` mid-run to simulate another process eating space.
    """

    def __init__(self, root: Path, capacity: int) -> None:
        self.root = root
        self.capacity = capacity
        self.foreign_debit = 0

    def __call__(self, path: Path) -> int:
        used = sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file())
        return max(0, self.capacity - used - self.foreign_debit)


def _storage_engine(
    target: Path, *, mode: TargetMode, reserve: int, percent=None, types=("dat",)
) -> ChaffEngine:
    from conftest import make_config

    target.mkdir(parents=True, exist_ok=True)
    config = replace(
        make_config(target),
        target=TargetSpec(path=target, mode=mode, amount=None, percent=percent, reserve=reserve),
        profile="storage-test",
        file_types={fmt: FileTypeSetting(enabled=True) for fmt in types},
    )
    return ChaffEngine(config)


def _payload_context(tmp_path: Path, seed: int, desired: int) -> RenderContext:
    from conftest import make_config

    bank = load_default_pack()
    world = build_world(481_925, make_config(tmp_path / "world"), bank, estimated_files=5)
    rng = random.Random(seed)
    return RenderContext(
        rng=rng,
        world=world,
        bank=bank,
        template_engine=ChaffTemplateEngine(world=world, bank=bank, rng=rng),
        desired_size=desired,
        run_id="t",
        app_version="0.1.0",
        file_seed=seed,
    )


class TestPayloadRenderer:
    @pytest.mark.parametrize(
        ("size", "seed"),
        [(1, 101), (CHUNK_BYTES, 102), (3 * CHUNK_BYTES + 12_345, 103), (511, 104)],
    )
    def test_lands_exactly_and_hashes(self, tmp_path: Path, size: int, seed: int):
        ctx = _payload_context(tmp_path, seed, size)
        dest = tmp_path / f"payload-{size}-{seed}.dat"
        result = build_registry().get("dat").render(None, dest, ctx)
        assert dest.stat().st_size == size == result.size

        # Hash matches an independent shake_256 recomputation.
        digest = hashlib.sha256()
        written = 0
        index = 0
        while written < size:
            chunk = _chunk(seed, index)
            digest.update(chunk[: min(len(chunk), size - written)])
            written += len(chunk)
            index += 1
        assert result.sha256 == digest.hexdigest()

    def test_deterministic_and_seed_sensitive(self, tmp_path: Path):
        def render(seed: int) -> bytes:
            dest = tmp_path / f"p-{seed}.dat"
            build_registry().get("dat").render(
                None, dest, _payload_context(tmp_path, seed, 100_000)
            )
            return dest.read_bytes()

        first, second, other = render(7), render(7), render(8)
        assert first == second
        assert first != other

    def test_chunk_stream_repeats_across_files(self):
        """Two payloads of equal size share chunks only when their seeds
        match: the chunk index counter keeps distinct files distinct."""
        assert _chunk(1, 0) != _chunk(2, 0)
        assert _chunk(1, 0) != _chunk(1, 1)
        assert len(_chunk(1, 5)) == CHUNK_BYTES

    @pytest.mark.skipif(sys.platform == "win32", reason="st_blocks is POSIX-only")
    def test_payload_is_not_sparse(self, tmp_path: Path):
        """Payloads must be real blocks, not sparse holes (spec section 22)."""
        dest = tmp_path / "sparse-check.dat"
        build_registry().get("dat").render(None, dest, _payload_context(tmp_path, 42, 2 * MIB))
        stat = dest.stat()
        assert stat.st_blocks * 512 >= stat.st_size


class TestFillModes:
    def test_fill_until_reserve_stops_at_reserve(self, tmp_path: Path, monkeypatch):
        disk = FakeDisk(tmp_path, capacity=6 * MIB)
        monkeypatch.setattr("chaff_generator.core.filesystem.free_bytes", disk)
        engine = _storage_engine(tmp_path, mode=TargetMode.FILL_UNTIL_RESERVE, reserve=4 * MIB)

        result = engine.generate()
        assert result.status is RunStatus.COMPLETED
        # 2 MiB was available above the reserve; dat lands exactly, so the
        # run should write (almost) exactly that and leave >= reserve free.
        assert result.bytes_written <= 2 * MIB
        assert result.bytes_written >= 1 * MIB
        assert disk(tmp_path) >= 4 * MIB - (64 << 10)  # journal/marker overhead

    def test_percent_free_targets_fraction_of_free(self, tmp_path: Path, monkeypatch):
        disk = FakeDisk(tmp_path, capacity=10 * MIB)
        monkeypatch.setattr("chaff_generator.core.filesystem.free_bytes", disk)
        engine = _storage_engine(
            tmp_path,
            mode=TargetMode.PERCENT_FREE,
            reserve=1 * MIB,
            percent=Decimal("50"),
        )

        expected = (10 * MIB - 1 * MIB) // 2  # (free - reserve) * 50%
        summary = engine.preflight()
        assert summary.requested_bytes == expected

        result = engine.generate()
        assert result.status is RunStatus.COMPLETED
        # generate() recomputes the target after the marker/journal exist,
        # so the exact byte count sits within a small overhead of expected.
        assert abs(result.bytes_written - expected) <= 8 << 10
        assert disk(tmp_path) >= 1 * MIB - (64 << 10)

    def test_foreign_writer_stops_run_at_reserve(self, tmp_path: Path, monkeypatch):
        """Another process eating space mid-run must stop chaff at the
        reserve (monitor truth wins over the logical counter, section 58)."""
        disk = FakeDisk(tmp_path, capacity=8 * MIB)
        monkeypatch.setattr("chaff_generator.core.filesystem.free_bytes", disk)
        engine = _storage_engine(
            tmp_path,
            mode=TargetMode.PERCENT_FREE,
            reserve=1 * MIB,
            percent=Decimal("80"),
            types=("txt",),  # small files: many boundaries for the debit to bite
        )

        original_emit = engine._emit

        def eat_space_and_forward(event: object) -> None:
            original_emit(event)
            if isinstance(event, FileCompleted):
                disk.foreign_debit = 5 * MIB  # foreign writer consumes space

        engine._emit = eat_space_and_forward  # type: ignore[method-assign]
        result = engine.generate()
        assert result.status is RunStatus.COMPLETED  # graceful, not FAILED
        assert result.bytes_written < int(7 * MIB * 0.8)
        assert any("reserve" in w.lower() for w in result.warnings)
        assert disk(tmp_path) >= 1 * MIB - (64 << 10)

    def test_exact_mode_never_crosses_reserve(self, tmp_path: Path, monkeypatch):
        disk = FakeDisk(tmp_path, capacity=4 * MIB)
        monkeypatch.setattr("chaff_generator.core.filesystem.free_bytes", disk)
        from conftest import make_config

        target = tmp_path / "t"
        target.mkdir()
        config = replace(
            make_config(target),
            target=TargetSpec(path=target, mode=TargetMode.EXACT, amount=10 * MIB, reserve=2 * MIB),
            profile="storage-test",
            file_types={"dat": FileTypeSetting(enabled=True)},
        )
        result = ChaffEngine(config).generate()
        assert result.status is RunStatus.FAILED
        assert result.error is not None and "free space" in result.error.lower()
        assert disk(target) >= 2 * MIB - (64 << 10)  # reserve honored


class TestCliFillFlags:
    def test_exactly_one_mode_flag(self, tmp_path: Path):
        from chaff_generator.cli.generate import _build_config

        with pytest.raises(Exception, match="exactly one"):
            _build_config(
                target=tmp_path,
                size=None,
                percent_free=None,
                fill_free_space=False,
                reserve="2 GB",
                profile="storage-test",
                types=None,
                layout="simple",
                completion="keep",
                seed=1,
                config_path=None,
            )

    def test_percent_free_config_shape(self, tmp_path: Path):
        from chaff_generator.cli.generate import _build_config

        config = _build_config(
            target=tmp_path,
            size=None,
            percent_free=25.0,
            fill_free_space=False,
            reserve="1 GB",
            profile="storage-test",
            types="dat",
            layout="simple",
            completion="keep",
            seed=1,
            config_path=None,
        )
        assert config.target.mode is TargetMode.PERCENT_FREE
        assert str(config.target.percent) == "25.0"
        assert config.target.reserve == 1 * 10**9

    def test_fill_free_space_config_shape(self, tmp_path: Path):
        from chaff_generator.cli.generate import _build_config

        config = _build_config(
            target=tmp_path,
            size=None,
            percent_free=None,
            fill_free_space=True,
            reserve="512 MiB",
            profile="storage-test",
            types=None,
            layout="simple",
            completion="keep",
            seed=1,
            config_path=None,
        )
        assert config.target.mode is TargetMode.FILL_UNTIL_RESERVE


class TestBenchmarkGuard:
    def test_refuses_without_acknowledgement(self, tmp_path: Path):
        script = Path(__file__).resolve().parents[2] / "scripts" / "benchmark.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--target", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode != 0
        assert "i-understand-this-writes" in proc.stderr

"""Planner tests: pool resolution, size distribution, paths, finalizer tail."""

from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from chaff_generator.core.models import FileTypeSetting, GenerationConfig, LayoutMode
from chaff_generator.core.planner import (
    MIN_FINALIZER_BYTES,
    Planner,
    estimate_file_count,
    plan_seed,
)
from chaff_generator.renderers.base import RendererCapabilities

_EXACT_CAPS = RendererCapabilities(
    extension="x",
    supports_exact_size=True,
    supports_target_size=True,
    supports_streaming=True,
    semantic_document=None,
    size_category="x",
)
_APPROX_CAPS = RendererCapabilities(
    extension="x",
    supports_exact_size=False,
    supports_target_size=True,
    supports_streaming=True,
    semantic_document=None,
    size_category="x",
)


def _caps(*formats: str) -> dict[str, RendererCapabilities]:
    return {fmt: _EXACT_CAPS for fmt in formats}


def make_planner(
    config: GenerationConfig,
    bank,  # type: ignore[no-untyped-def]
    world,  # type: ignore[no-untyped-def]
    capabilities: dict[str, RendererCapabilities] | None = None,
):
    from chaff_generator.profiles.loader import resolve_profile

    profile = resolve_profile(config.profile, bank.profiles())
    if capabilities is None:
        # Every format the profile knows, exact-size capable.
        capabilities = {fmt: _EXACT_CAPS for fmt in profile.format_weights}
    return Planner(
        config=config,
        profile=profile,
        bank=bank,
        world=world,
        templates=bank.templates(),
        capabilities=capabilities,
    )


class TestSeed:
    def test_domain_separated(self):
        assert plan_seed(481_925) != 481_925
        assert plan_seed(1) != plan_seed(2)

    def test_stable(self):
        assert plan_seed(481_925) == plan_seed(481_925)


class TestEstimate:
    def test_zero_volume(self):
        assert estimate_file_count(0, {"txt": 1}) == 0

    def test_scales_with_volume(self):
        small = estimate_file_count(1 << 20, {"txt": 1})
        large = estimate_file_count(64 << 20, {"txt": 1})
        assert large > small >= 1

    def test_empty_pool(self):
        assert estimate_file_count(1 << 20, {}) == 0


class TestPoolResolution:
    def test_config_types_override_profile(self, default_bank, world, config: GenerationConfig):
        from dataclasses import replace

        cfg = replace(
            config,
            file_types={"txt": FileTypeSetting(enabled=True), "csv": FileTypeSetting(enabled=True)},
        )
        planner = make_planner(cfg, default_bank, world)
        assert set(planner._pool) == {"txt", "csv"}

    def test_unavailable_formats_pruned(self, default_bank, world, config):
        planner = make_planner(config, default_bank, world, capabilities={"txt": _EXACT_CAPS})
        assert set(planner._pool) == {"txt"}

    def test_empty_pool_raises(self, default_bank, world, config):
        from chaff_generator.core.errors import ConfigurationError

        with pytest.raises(ConfigurationError):
            make_planner(config, default_bank, world, capabilities={})


class TestPlanning:
    def test_stop_below_dust_threshold(self, default_bank, world, config):
        planner = make_planner(config, default_bank, world)
        assert planner.next_file(index=99, remaining=MIN_FINALIZER_BYTES - 1) is None

    def test_plan_is_deterministic(self, default_bank, world, config, tmp_path):
        def plan_all():  # type: ignore[no-untyped-def]
            planner = make_planner(config, default_bank, world)
            out = []
            remaining = 1 << 20
            index = 0
            while remaining >= MIN_FINALIZER_BYTES and len(out) < 500:
                planned = planner.next_file(index, remaining)
                assert planned is not None
                out.append(planned)
                remaining -= min(planned.desired_size, remaining)
                index += 1
            return out

        first, second = plan_all(), plan_all()
        assert [(p.relative_path, p.desired_size, p.seed) for p in first] == [
            (p.relative_path, p.desired_size, p.seed) for p in second
        ]

    def test_paths_are_posix_relative(self, default_bank, world, config):
        planner = make_planner(config, default_bank, world)
        for index in range(40):
            planned = planner.next_file(index, remaining=1 << 20)
            assert planned is not None
            assert planned.relative_path == PurePosixPath(planned.relative_path).as_posix()
            assert not planned.relative_path.startswith("/")
            assert ".." not in planned.relative_path.split("/")

    def test_no_path_collisions(self, default_bank, world, config):
        planner = make_planner(config, default_bank, world)
        seen: set[str] = set()
        for index in range(200):
            planned = planner.next_file(index, remaining=1 << 30)
            assert planned is not None
            assert planned.relative_path not in seen, "allocator handed out a duplicate path"
            seen.add(planned.relative_path)

    def test_dev_files_get_extensions(self, default_bank, world, config):
        """The dev renderer cycles real extensions; filenames must match."""
        from dataclasses import replace

        cfg = replace(config, file_types={"dev": FileTypeSetting(enabled=True)})
        planner = make_planner(cfg, default_bank, world, capabilities={"dev": _EXACT_CAPS})
        kinds: set[str] = set()
        for index in range(16):
            planned = planner.next_file(index, remaining=1 << 30)
            assert planned is not None
            assert planned.renderer_id == "dev"
            name = planned.relative_path.rsplit("/", 1)[-1]
            assert "." in name or name.startswith("Dockerfile"), f"dev file {name} has no kind"
            kinds.add(name.rsplit(".", 1)[-1] if "." in name else "dockerfile")
        assert len(kinds) >= 3, "dev extension menu did not cycle"

    def test_log_uniform_distribution(self):
        """Log-uniform draws: the median sits near the geometric mean, and
        small files are far more common than a uniform draw would make them."""
        import math
        import random

        from chaff_generator.core.planner import _log_uniform

        rng = random.Random(481_925)
        lo, hi = 4 << 10, 64 << 20
        draws = [_log_uniform(rng, lo, hi) for _ in range(2_000)]
        assert all(lo <= d <= hi for d in draws)
        median = sorted(draws)[len(draws) // 2]
        geo_mean = math.isqrt(lo * hi)
        assert geo_mean * 0.5 < median < geo_mean * 2
        # Uniform would put ~2.3% below 1 MiB; log-uniform puts ~46% there.
        below_1m = sum(1 for d in draws if d < (1 << 20)) / len(draws)
        assert below_1m > 0.3, f"distribution not small-heavy: {below_1m:.2%} below 1 MiB"

    def test_log_uniform_degenerate_range(self):
        import random

        from chaff_generator.core.planner import _log_uniform

        rng = random.Random(1)
        assert _log_uniform(rng, 100, 100) == 100
        assert _log_uniform(rng, 200, 100) == 100

    def test_finalizer_lands_exact_tail(self, default_bank, world, config):
        """When a draw exceeds the remainder, the plan switches to an
        exact-size renderer and lands precisely on the remaining bytes."""
        planner = make_planner(config, default_bank, world)
        remaining = 1 << 20
        index = 0
        last: int | None = None
        while remaining >= MIN_FINALIZER_BYTES and index < 500:
            planned = planner.next_file(index, remaining)
            assert planned is not None
            assert planned.desired_size <= remaining, "plan overshoots the remainder"
            remaining -= planned.desired_size
            last = planned.desired_size
            index += 1
        assert remaining == 0, f"run stopped short by {remaining} bytes"
        assert last is not None

    def test_approximate_tail_clamped(self, default_bank, world, config):
        """Without exact renderers the tail is clamped to the remainder."""
        caps = {"md": _APPROX_CAPS, "html": _APPROX_CAPS}
        planner = make_planner(config, default_bank, world, capabilities=caps)
        planned = planner.next_file(index=0, remaining=5_000)
        assert planned is not None
        assert planned.desired_size <= 5_000


class TestLayouts:
    def test_flat_layout_has_no_directories(self, default_bank, world, config):
        from dataclasses import replace

        cfg = replace(config, directory_layout=LayoutMode.FLAT)
        planner = make_planner(cfg, default_bank, world)
        for index in range(30):
            planned = planner.next_file(index, remaining=1 << 20)
            assert planned is not None
            assert "/" not in planned.relative_path

    def test_simple_layout_uses_known_roots(self, default_bank, world, config):
        from dataclasses import replace

        cfg = replace(config, directory_layout=LayoutMode.SIMPLE)
        planner = make_planner(cfg, default_bank, world)
        known = {"Spreadsheets", "Logs", "Data", "Code", "Mail", "Personal", "Documents"}
        for index in range(60):
            planned = planner.next_file(index, remaining=1 << 20)
            assert planned is not None
            parts = planned.relative_path.split("/")
            assert parts[0] in known, f"unexpected simple-layout root {parts[0]!r}"

    def test_realistic_layout_varies(self, default_bank, world, config):
        planner = make_planner(config, default_bank, world)
        roots: set[str] = set()
        for index in range(120):
            planned = planner.next_file(index, remaining=1 << 20)
            assert planned is not None
            roots.add(planned.relative_path.split("/")[0])
        assert len(roots) >= 3, "realistic layout produced a single root"

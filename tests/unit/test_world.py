"""Generation world: determinism, coherence, and synthetic-only guarantees."""

from __future__ import annotations

import itertools
import random
from datetime import date
from pathlib import Path

import pytest
from tests.conftest import TEST_SEED, make_config

from chaff_generator.content.bank import ChaffBank
from chaff_generator.content.generators import RecentTracker, make_email, make_phone, pick
from chaff_generator.content.world import build_world


class TestWorld:
    def test_deterministic(self, default_bank: ChaffBank, tmp_path: Path) -> None:
        world_a = build_world(TEST_SEED, make_config(tmp_path), default_bank, estimated_files=60)
        world_b = build_world(TEST_SEED, make_config(tmp_path), default_bank, estimated_files=60)
        assert world_a.organization.name == world_b.organization.name
        assert [p.id for p in world_a.projects] == [p.id for p in world_b.projects]
        assert [p.email for p in world_a.employees] == [p.email for p in world_b.employees]

    def test_different_seed_different_world(self, default_bank: ChaffBank, tmp_path: Path) -> None:
        world_a = build_world(1, make_config(tmp_path), default_bank, estimated_files=60)
        world_b = build_world(2, make_config(tmp_path), default_bank, estimated_files=60)
        assert world_a.organization.name != world_b.organization.name

    def test_emails_are_non_routable(self, default_bank: ChaffBank, tmp_path: Path) -> None:
        world = build_world(TEST_SEED, make_config(tmp_path), default_bank)
        for person in (world.primary_user, *world.employees, *world.contacts):
            local, _, domain = person.email.rpartition("@")
            assert local
            assert domain.endswith(".example") or domain == "example.com", person.email

    def test_dates_within_configured_range(self, default_bank: ChaffBank, tmp_path: Path) -> None:
        world = build_world(TEST_SEED, make_config(tmp_path), default_bank)
        start, end = date(2023, 1, 1), date(2026, 8, 1)
        for person in world.employees:
            assert start <= person.hire_date <= end
        for project in world.projects:
            assert start <= project.start_date <= end
            if project.end_date is not None:
                assert project.start_date < project.end_date

    def test_project_managers_exist(self, default_bank: ChaffBank, tmp_path: Path) -> None:
        world = build_world(TEST_SEED, make_config(tmp_path), default_bank)
        for project in world.projects:
            assert world.person_by_id(project.manager_id) is not None

    def test_counts_scale_with_volume(self, default_bank: ChaffBank, tmp_path: Path) -> None:
        small = build_world(TEST_SEED, make_config(tmp_path), default_bank, estimated_files=10)
        large = build_world(TEST_SEED, make_config(tmp_path), default_bank, estimated_files=2000)
        assert len(small.employees) < len(large.employees)
        assert len(small.projects) <= len(large.projects)

    def test_any_person_pool(self, default_bank: ChaffBank, tmp_path: Path) -> None:
        world = build_world(TEST_SEED, make_config(tmp_path), default_bank)
        rng = random.Random(7)
        for _ in range(10):
            assert world.any_person(rng) in [world.primary_user, *world.employees]


class TestGenerators:
    def test_pick_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            pick(random.Random(1), ())

    def test_make_email_cleans_input(self) -> None:
        assert make_email("Alice O'Neal!", "example.com") == "aliceoneal@example.com"
        assert make_email("Ada Lovelace", "example.com") == "adalovelace@example.com"

    def test_make_phone_uses_555(self) -> None:
        assert "555-" in make_phone(random.Random(3))

    def test_recent_tracker_avoids_repeats(self) -> None:
        rng = random.Random(11)
        tracker = RecentTracker(window=5, max_rerolls=3)
        pool = tuple(range(50))
        draws = [tracker.pick(rng, pool) for _ in range(20)]
        immediate_repeats = sum(1 for a, b in itertools.pairwise(draws) if a == b)
        assert immediate_repeats <= 4  # occasional repeats allowed, not constant

    def test_recent_tracker_allows_repeats_in_small_pools(self) -> None:
        rng = random.Random(2)
        tracker = RecentTracker(window=4, max_rerolls=2)
        pool = (1, 2)
        draws = [tracker.pick(rng, pool) for _ in range(20)]
        assert len(draws) == 20  # never deadlocks on tiny pools

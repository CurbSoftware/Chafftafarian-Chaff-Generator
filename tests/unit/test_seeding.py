"""Seed derivation stability (spec section 11)."""

from __future__ import annotations

from chaff_generator.core.seeding import derive_file_seed, new_master_seed


def test_derive_file_seed_stable() -> None:
    assert derive_file_seed(481_925, 0) == derive_file_seed(481_925, 0)
    assert derive_file_seed(481_925, 7) == derive_file_seed(481_925, 7)


def test_derive_file_seed_varies_by_index() -> None:
    seeds = {derive_file_seed(481_925, i) for i in range(50)}
    assert len(seeds) == 50


def test_derive_file_seed_varies_by_master() -> None:
    assert derive_file_seed(1, 0) != derive_file_seed(2, 0)


def test_derive_file_seed_domain_separated_from_world() -> None:
    # File seeds must not collide with the world seed derivation.
    from chaff_generator.content.world import world_seed

    assert derive_file_seed(481_925, 0) != world_seed(481_925)


def test_new_master_seed_random_and_64bit() -> None:
    seeds = {new_master_seed() for _ in range(20)}
    assert len(seeds) == 20
    assert all(0 <= seed < 2**64 for seed in seeds)

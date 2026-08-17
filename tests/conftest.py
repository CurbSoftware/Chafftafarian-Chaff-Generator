"""Shared fixtures: default pack, config, and a small deterministic world."""

from __future__ import annotations

import os

# GUI tests run headless: decide the Qt platform before anything imports Qt.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import date
from pathlib import Path

import pytest

from chaff_generator.content.bank import ChaffBank, default_pack_path
from chaff_generator.content.world import GenerationWorld, build_world
from chaff_generator.core.models import (
    DateRange,
    GenerationConfig,
    TargetMode,
    TargetSpec,
)

TEST_SEED = 481_925


def make_config(target: Path) -> GenerationConfig:
    """A minimal valid EXACT-mode config pointing at a temp directory."""
    return GenerationConfig(
        schema_version=1,
        target=TargetSpec(path=target, mode=TargetMode.EXACT, amount=1024),
        seed=TEST_SEED,
        date_range=DateRange(date(2023, 1, 1), date(2026, 8, 1)),
    )


@pytest.fixture(scope="session")
def default_bank() -> ChaffBank:
    return ChaffBank.load(default_pack_path())


@pytest.fixture()
def config(tmp_path: Path) -> GenerationConfig:
    return make_config(tmp_path)


@pytest.fixture(scope="session")
def world(default_bank: ChaffBank, tmp_path_factory: pytest.TempPathFactory) -> GenerationWorld:
    target = tmp_path_factory.mktemp("world-target")
    return build_world(TEST_SEED, make_config(target), default_bank, estimated_files=60)

"""Config model construction, validation, and round-trips."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from chaff_generator.core.errors import ConfigurationError
from chaff_generator.core.models import (
    CompletionAction,
    DateRange,
    FileTypeSetting,
    GenerationConfig,
    LayoutMode,
    TargetMode,
    TargetSpec,
    config_to_dict,
    dict_to_config,
)


def base_target(tmp_path: Path) -> TargetSpec:
    return TargetSpec(path=tmp_path, mode=TargetMode.EXACT, amount=10_000_000)


class TestValidation:
    def test_exact_requires_amount(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError):
            TargetSpec(path=tmp_path, mode=TargetMode.EXACT, amount=0)

    def test_percent_requires_percent(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError):
            TargetSpec(path=tmp_path, mode=TargetMode.PERCENT_FREE)

    def test_negative_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError):
            TargetSpec(path=tmp_path, mode=TargetMode.EXACT, amount=-1)

    def test_date_range_order(self) -> None:
        with pytest.raises(ConfigurationError):
            DateRange(date(2026, 1, 1), date(2023, 1, 1))

    def test_negative_weight(self) -> None:
        with pytest.raises(ConfigurationError):
            FileTypeSetting(enabled=True, weight=-3)


class TestRoundTrip:
    def test_dict_round_trip(self, tmp_path: Path) -> None:
        config = GenerationConfig(
            schema_version=1,
            target=base_target(tmp_path),
            profile="realistic-desktop",
            seed=481_925,
            date_range=DateRange(date(2024, 2, 1), date(2026, 3, 31)),
            directory_layout=LayoutMode.REALISTIC,
            file_types={"txt": FileTypeSetting(True, 20), "pdf": FileTypeSetting(False)},
            completion=CompletionAction.TRASH,
        )
        rebuilt = dict_to_config(config_to_dict(config))
        assert rebuilt == config

    def test_yaml_and_json_round_trip(self, tmp_path: Path) -> None:
        from chaff_generator.core.models import dump_config, load_config

        config = GenerationConfig(
            schema_version=1,
            target=base_target(tmp_path),
            seed=42,
        )
        yaml_path = tmp_path / "preset.yaml"
        json_path = tmp_path / "preset.json"
        dump_config(config, yaml_path)
        dump_config(config, json_path)
        assert load_config(yaml_path) == config
        assert load_config(json_path) == config

    def test_amount_accepts_size_strings(self, tmp_path: Path) -> None:
        data = {
            "schema_version": 1,
            "target": {"path": str(tmp_path), "mode": "exact", "amount": "1.5 GiB"},
        }
        config = dict_to_config(data)
        assert config.target.amount == 1_610_612_736

    def test_future_schema_version_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError):
            dict_to_config({"schema_version": 2, "target": {"path": str(tmp_path)}})

    def test_unknown_enum_values_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError):
            dict_to_config(
                {
                    "schema_version": 1,
                    "target": {"path": str(tmp_path)},
                    "directory_layout": "fancy",
                }
            )

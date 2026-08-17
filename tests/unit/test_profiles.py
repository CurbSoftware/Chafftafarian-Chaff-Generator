"""Profile loading and resolution."""

from __future__ import annotations

import pytest

from chaff_generator.core.errors import ConfigurationError
from chaff_generator.profiles.builtin import BUILTIN_PROFILES
from chaff_generator.profiles.loader import parse_profile, resolve_profile
from chaff_generator.profiles.models import parse_size_ranges


class TestParseProfile:
    def test_minimal_profile(self) -> None:
        profile = parse_profile({"id": "mini", "format_weights": {"txt": 5, "pdf": 3}})
        assert profile.id == "mini"
        assert profile.name == "Mini"
        assert profile.format_weights == {"txt": 5, "pdf": 3}
        assert profile.avg_file_size_bytes > 0

    def test_size_profile_accepts_unit_strings(self) -> None:
        ranges = parse_size_ranges({"dat": {"min": "1 MiB", "max": "4 GiB"}})
        assert ranges["dat"].min_bytes == 1 << 20
        assert ranges["dat"].max_bytes == 4 << 30

    def test_size_profile_accepts_plain_ints(self) -> None:
        ranges = parse_size_ranges({"txt": {"min": 1024, "max": 2048}})
        assert ranges["txt"].max_bytes == 2048

    def test_invalid_size_rejected(self) -> None:
        with pytest.raises(ConfigurationError):
            parse_size_ranges({"txt": {"min": "garbage", "max": 100}})

    def test_empty_format_weights_rejected(self) -> None:
        with pytest.raises(ConfigurationError):
            parse_profile({"id": "bad", "format_weights": {}})

    def test_pack_profiles_load(self, default_bank) -> None:
        profiles = default_bank.profiles()
        assert "realistic-desktop" in profiles
        assert "storage-test" in profiles
        assert profiles["storage-test"].payload_default is True


class TestResolveProfile:
    def test_pack_profile_wins(self, default_bank) -> None:
        profile = resolve_profile("realistic-desktop", default_bank.profiles())
        assert profile.id == "realistic-desktop"

    def test_builtin_fallback(self, default_bank) -> None:
        profile = resolve_profile("mixed", default_bank.profiles())
        assert profile.id == "mixed"

    def test_unknown_falls_back_to_mixed(self, default_bank) -> None:
        profile = resolve_profile("does-not-exist", default_bank.profiles())
        assert profile.id == "mixed"

    def test_builtin_registry_covers_all_documented(self) -> None:
        expected = {
            "realistic-desktop",
            "office-workstation",
            "personal-computer",
            "developer-workstation",
            "balanced",
            "storage-test",
            "mixed",
        }
        assert expected <= set(BUILTIN_PROFILES)

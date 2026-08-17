"""Profile loading from pack YAML files, with builtin fallbacks (spec §69)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from chaff_generator.core.errors import ConfigurationError
from chaff_generator.core.models import LayoutMode
from chaff_generator.profiles.builtin import BUILTIN_PROFILES
from chaff_generator.profiles.models import (
    DEFAULT_AVG_SIZES,
    DEFAULT_SIZE_RANGES,
    Profile,
    SizeRange,
    parse_size_ranges,
)


def parse_profile(data: dict[str, Any]) -> Profile:
    """Build a Profile from a parsed YAML mapping."""
    try:
        profile_id = str(data["id"])
        name = str(data.get("name", profile_id.replace("-", " ").title()))
    except KeyError as exc:
        raise ConfigurationError(f"Profile is missing 'id': {exc}") from exc

    layout_raw = str(data.get("directory_layout", "realistic"))
    try:
        layout = LayoutMode(layout_raw)
    except ValueError as exc:
        raise ConfigurationError(f"Profile {profile_id}: unknown layout {layout_raw!r}") from exc

    format_weights = {str(k): int(v) for k, v in (data.get("format_weights") or {}).items()}
    if not format_weights:
        raise ConfigurationError(f"Profile {profile_id}: format_weights must not be empty")

    content_domains = {str(k): int(v) for k, v in (data.get("content_domains") or {}).items()}

    size_profile = {**DEFAULT_SIZE_RANGES, **parse_size_ranges(data.get("size_profile"))}
    avg_file_size = int(data.get("avg_file_size_bytes", 0)) or _weighted_average(
        format_weights, size_profile
    )

    return Profile(
        id=profile_id,
        name=name,
        description=str(data.get("description", "")),
        directory_layout=layout,
        format_weights=format_weights,
        content_domains=content_domains,
        size_profile=size_profile,
        avg_file_size_bytes=avg_file_size,
        payload_default=bool(data.get("payload_default", False)),
    )


def _weighted_average(weights: dict[str, int], sizes: dict[str, SizeRange]) -> int:
    total_weight = sum(weights.values()) or 1
    total = 0
    for format_id, weight in weights.items():
        default = DEFAULT_AVG_SIZES.get(format_id)
        if default is not None:
            total += weight * default
        elif format_id in sizes:
            total += weight * (sizes[format_id].min_bytes + sizes[format_id].max_bytes) // 2
    return max(1, total // total_weight)


def load_profiles(pack_dir: Path) -> dict[str, Profile]:
    """Load every ``<pack>/profiles/*.yaml`` file."""
    profiles: dict[str, Profile] = {}
    profiles_dir = pack_dir / "profiles"
    if not profiles_dir.is_dir():
        return profiles
    for file in sorted(profiles_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(file.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigurationError(f"{file.name}: invalid YAML — {exc}") from exc
        if isinstance(data, dict):
            profile = parse_profile(data)
            profiles[profile.id] = profile
    return profiles


def resolve_profile(profile_id: str, pack_profiles: dict[str, Profile]) -> Profile:
    """Resolve a profile id against pack profiles, then builtins.

    ``mixed`` is the fallback when the id matches nothing.
    """
    if profile_id in pack_profiles:
        return pack_profiles[profile_id]
    if profile_id in BUILTIN_PROFILES:
        return BUILTIN_PROFILES[profile_id]
    if "mixed" in pack_profiles:
        return pack_profiles["mixed"]
    if "mixed" in BUILTIN_PROFILES:
        return BUILTIN_PROFILES["mixed"]
    raise ConfigurationError(f"Profile not found: {profile_id}")

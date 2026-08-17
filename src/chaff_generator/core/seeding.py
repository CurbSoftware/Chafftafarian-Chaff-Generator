"""Deterministic seed derivation (spec section 11).

A run has one master seed. Every planned file derives an independent,
reproducible seed from the master seed and the file's index via a
domain-separated SHA-256, so generation order, retries, or parallelism never
change which random values belong to which file.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Final

_DOMAIN: Final = "chaff-file-seed:v1"


def derive_file_seed(master_seed: int, index: int) -> int:
    """Derive a 128-bit file seed from the master seed and file index."""
    if master_seed < 0:
        raise ValueError("master_seed must be non-negative")
    if index < 0:
        raise ValueError("index must be non-negative")
    digest = hashlib.sha256(f"{_DOMAIN}:{master_seed}:{index}".encode()).digest()
    return int.from_bytes(digest[:16], "big")


def new_master_seed() -> int:
    """Generate a fresh cryptographically random 64-bit master seed."""
    return secrets.randbits(64)

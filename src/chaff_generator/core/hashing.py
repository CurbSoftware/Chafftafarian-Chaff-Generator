"""Streaming SHA-256 helpers.

Files are hashed in fixed-size chunks; multi-gigabyte payloads never sit in
memory (spec section 60).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO, Final

CHUNK_SIZE: Final[int] = 1 << 20  # 1 MiB

#: Algorithms accepted in manifests / configuration.
SUPPORTED_ALGORITHMS: Final[frozenset[str]] = frozenset({"sha256"})


def hash_file(path: Path, algorithm: str = "sha256") -> str:
    """Stream a file through hashlib and return the hex digest."""
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


class HashingWriter:
    """Wrapper around a binary file object that digests everything written."""

    def __init__(self, handle: BinaryIO, algorithm: str = "sha256") -> None:
        if algorithm not in SUPPORTED_ALGORITHMS:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
        self._handle = handle
        self._digest = hashlib.new(algorithm)
        self._bytes_written = 0

    @property
    def bytes_written(self) -> int:
        """Total bytes passed through this writer."""
        return self._bytes_written

    @property
    def digest_hex(self) -> str:
        """Hex digest of everything written so far."""
        return self._digest.hexdigest()

    def write(self, data: bytes) -> int:
        written = self._handle.write(data)
        self._digest.update(data)
        self._bytes_written += written
        return written

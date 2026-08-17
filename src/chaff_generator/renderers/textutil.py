"""Shared streaming text writers for renderers.

All renderers write in binary mode with explicit ``\\n`` newlines (spec
section 12) so output is byte-identical on Windows, Linux, and macOS, and
hash as they write via :class:`HashingWriter`.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from chaff_generator.core.filesystem import fsync_file
from chaff_generator.core.hashing import HashingWriter

if TYPE_CHECKING:
    from pathlib import Path
    from typing import BinaryIO


def utf8_prefix(data: bytes, limit: int) -> int:
    """Largest length ``<= limit`` that ends on a UTF-8 character boundary."""
    if limit >= len(data):
        return len(data)
    cut = limit
    # Continuation bytes are 0b10xxxxxx; walk back at most 3 to a start byte.
    while cut > 0 and (data[cut] & 0xC0) == 0x80:
        cut -= 1
    return cut


def open_writer(destination: Path) -> tuple[BinaryIO, HashingWriter]:
    """Open ``destination`` for binary writing wrapped in a hashing writer.

    The caller owns the handle and must close it (close-before-rename keeps
    Windows file locks out of the engine's ``os.replace``).
    """
    handle = destination.open("wb")
    return handle, HashingWriter(handle)


def finish(handle: BinaryIO) -> None:
    """Flush and fsync inside the ``with`` block before the caller closes."""
    handle.flush()
    fsync_file(handle)


def write_chunks_exact(writer: HashingWriter, chunks: Iterable[str], desired: int) -> None:
    """Write UTF-8 chunks until *exactly* ``desired`` bytes are written.

    The final chunk is cut on a character boundary and padded with spaces so
    the file lands precisely on the target byte count — the exact-size
    contract relied on by the planner's finalizer.
    """
    if desired < 0:
        raise ValueError(f"write_chunks_exact: negative desired size {desired}")
    remaining = desired
    for chunk in chunks:
        if remaining <= 0:
            return
        data = chunk.encode("utf-8")
        if len(data) <= remaining:
            writer.write(data)
            remaining -= len(data)
        else:
            cut = utf8_prefix(data, remaining)
            writer.write(data[:cut] + b" " * (remaining - cut))
            return
    if remaining > 0:
        # Generator ran dry (tiny target or empty document): pad with spaces.
        writer.write(b" " * remaining)


def write_chunks_until(writer: HashingWriter, chunks: Iterable[str], desired: int) -> None:
    """Write whole UTF-8 chunks while total bytes stay below ``desired``.

    Approximate-size landing: never splits a chunk, so the file may slightly
    overshoot the target — acceptable for formats whose structure would be
    corrupted by padding (csv rows, JSON arrays, XML tags).
    """
    for chunk in chunks:
        if writer.bytes_written >= desired:
            return
        writer.write(chunk.encode("utf-8"))

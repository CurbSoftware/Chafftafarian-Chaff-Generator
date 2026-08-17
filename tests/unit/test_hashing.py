"""Streaming hashing helpers."""

from __future__ import annotations

import hashlib

from chaff_generator.core.hashing import HashingWriter, hash_file


def test_hash_file_matches_hashlib(tmp_path):
    payload = b"chaff" * 1_000_003  # forces multiple 1 MiB chunks
    path = tmp_path / "blob.bin"
    path.write_bytes(payload)
    assert hash_file(path) == hashlib.sha256(payload).hexdigest()


def test_hash_file_empty(tmp_path):
    path = tmp_path / "empty.bin"
    path.write_bytes(b"")
    assert hash_file(path) == hashlib.sha256(b"").hexdigest()


def test_hashing_writer_digest_matches(tmp_path):
    with open(tmp_path / "out.bin", "wb") as handle:
        writer = HashingWriter(handle)
        writer.write(b"hello ")
        writer.write(b"world")
        assert writer.bytes_written == 11
        assert writer.digest_hex == hashlib.sha256(b"hello world").hexdigest()


def test_hashing_writer_flushes_to_disk(tmp_path):
    with open(tmp_path / "out.bin", "wb") as handle:
        writer = HashingWriter(handle)
        writer.write(b"abc")
        assert writer.digest_hex == hashlib.sha256(b"abc").hexdigest()
    assert (tmp_path / "out.bin").read_bytes() == b"abc"

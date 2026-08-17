"""Path sanitization, containment, and allocation safety."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

import pytest

from chaff_generator.core.errors import UnsafePathError
from chaff_generator.core.paths import (
    PathAllocator,
    check_path_length,
    is_within,
    safe_join,
    sanitize_filename,
    sanitize_relative_path,
    truncate_name,
)


class TestSanitizeFilename:
    def test_illegal_characters_replaced(self) -> None:
        assert sanitize_filename('a<b>c:"d/e\\f|g?h*i') == "a-b-c--d-e-f-g-h-i"

    def test_whitespace_collapsed(self) -> None:
        assert sanitize_filename("my   file\n name") == "my file- name"

    def test_trailing_dots_and_spaces_stripped(self) -> None:
        assert sanitize_filename("report. .txt. ") == "report. .txt"
        assert sanitize_filename("report.txt.. ") == "report.txt"
        assert sanitize_filename("no space ") == "no space"

    def test_windows_reserved_names(self) -> None:
        assert sanitize_filename("CON") == "CON_"
        assert sanitize_filename("con.txt") == "con_.txt"
        assert sanitize_filename("AUX.tar.gz") == "AUX_.tar.gz"
        assert sanitize_filename("COM1") == "COM1_"
        assert sanitize_filename("LPT9.log") == "LPT9_.log"

    def test_empty_becomes_untitled(self) -> None:
        assert sanitize_filename("...") == "untitled"
        assert sanitize_filename("   ") == "untitled"

    def test_truncation_keeps_extension(self) -> None:
        name = "a" * 200 + ".txt"
        result = sanitize_filename(name, max_length=50)
        assert len(result) <= 50
        assert result.endswith(".txt")

    def test_normal_names_unchanged(self) -> None:
        assert sanitize_filename("Quarterly Report 2026.docx") == "Quarterly Report 2026.docx"


class TestTruncateName:
    def test_short_names_untouched(self) -> None:
        assert truncate_name("notes.txt", 20) == "notes.txt"

    def test_long_names_keep_extension(self) -> None:
        result = truncate_name("x" * 300 + ".md", 40)
        assert len(result) == 40
        assert result.endswith(".md")

    def test_no_extension(self) -> None:
        assert len(truncate_name("y" * 300, 30)) == 30


class TestSanitizeRelativePath:
    def test_plain_relative(self) -> None:
        assert sanitize_relative_path("Documents/notes.txt") == PurePosixPath("Documents/notes.txt")

    @pytest.mark.parametrize("bad", ["../escape.txt", "/absolute.txt", "a/../../b.txt"])
    def test_traversal_and_absolute_rejected(self, bad: str) -> None:
        with pytest.raises(UnsafePathError):
            sanitize_relative_path(bad)


class TestContainment:
    def test_is_within(self, tmp_path: Path) -> None:
        child = tmp_path / "a" / "b.txt"
        assert is_within(child, tmp_path)
        assert not is_within(tmp_path / "c.txt", tmp_path / "other")

    def test_safe_join_plain(self, tmp_path: Path) -> None:
        joined = safe_join(tmp_path, "x/y.txt")
        assert joined == tmp_path / "x" / "y.txt"
        assert is_within(joined, tmp_path)

    def test_safe_join_rejects_traversal(self, tmp_path: Path) -> None:
        with pytest.raises(UnsafePathError):
            safe_join(tmp_path, "../outside.txt")

    def test_safe_join_rejects_absolute(self, tmp_path: Path) -> None:
        with pytest.raises(UnsafePathError):
            safe_join(tmp_path, "/etc/passwd")

    @pytest.mark.skipif(os.name != "posix", reason="symlink behavior checked on posix")
    def test_safe_join_rejects_symlink_escape(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "chaff-outside"
        outside.mkdir(exist_ok=True)
        link = tmp_path / "link"
        if link.exists() or link.is_symlink():
            link.unlink()
        os.symlink(outside, link)
        try:
            with pytest.raises(UnsafePathError):
                safe_join(tmp_path, "link/evil.txt")
        finally:
            link.unlink()
            outside.rmdir()


class TestPathAllocator:
    def test_case_insensitive_collision(self) -> None:
        allocator = PathAllocator()
        first = allocator.allocate(PurePosixPath("docs"), "Report.TXT")
        second = allocator.allocate(PurePosixPath("docs"), "report.txt")
        assert first.name == "Report.TXT"
        assert second.name == "report (2).txt"

    def test_deterministic_suffixes(self) -> None:
        allocator = PathAllocator()
        names = {allocator.allocate(PurePosixPath("d"), "same.txt").name for _ in range(3)}
        assert names == {"same.txt", "same (2).txt", "same (3).txt"}

    def test_different_directories_independent(self) -> None:
        allocator = PathAllocator()
        assert (
            allocator.allocate(PurePosixPath("a"), "f.txt").name
            == allocator.allocate(PurePosixPath("b"), "f.txt").name
        )


class TestPathLength:
    def test_short_path_clean(self, tmp_path: Path) -> None:
        assert check_path_length(tmp_path / "ok.txt") == []

    def test_long_path_flagged(self, tmp_path: Path) -> None:
        deep = tmp_path / ("z" * 200) / ("y" * 200) / "file.txt"
        assert check_path_length(deep) != []

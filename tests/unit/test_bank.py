"""ChaffBank loading, bank accessors, validation, and ZIP import safety."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from chaff_generator.content.bank import (
    ChaffBank,
    PackManager,
    validate_pack,
)
from chaff_generator.core.errors import PackError


class TestDefaultPack:
    def test_loads(self, default_bank: ChaffBank) -> None:
        assert default_bank.manifest.id == "builtin.en.general"
        assert default_bank.manifest.language == "en"

    def test_word_banks_populated(self, default_bank: ChaffBank) -> None:
        for category in ("nouns", "verbs", "adjectives", "adverbs", "topics"):
            assert len(default_bank.words(category)) >= 60, category

    def test_sentence_banks_populated(self, default_bank: ChaffBank) -> None:
        for category in ("business", "technical", "finance", "project_updates", "support"):
            assert len(default_bank.sentences(category)) >= 40, category

    def test_banks_skip_comments_and_blanks(self, default_bank: ChaffBank) -> None:
        assert all(not line.startswith("#") for line in default_bank.words("nouns"))

    def test_entity_banks(self, default_bank: ChaffBank) -> None:
        assert len(default_bank.entity_lines("first_names_male")) >= 400
        assert len(default_bank.entity_lines("job_titles")) >= 60
        products = default_bank.entity_json("products")
        assert isinstance(products, list) and len(products) >= 40

    def test_missing_bank_raises(self, default_bank: ChaffBank) -> None:
        with pytest.raises(PackError):
            default_bank.words("does-not-exist")

    def test_validate_pack_reports_ok(self, default_bank: ChaffBank) -> None:
        report = validate_pack(default_bank.root)
        assert report.ok, [f"{i.message}" for i in report.issues if i.severity == "error"]

    def test_missing_pack_yaml_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(PackError, match=r"pack\.yaml"):
            ChaffBank.load(tmp_path)


class TestPackManager:
    def _write_minimal_pack(self, root: Path) -> None:
        root.mkdir(parents=True)
        (root / "pack.yaml").write_text(
            "id: test.mini\nname: Mini\nversion: '1'\nlanguage: en\n",
            encoding="utf-8",
        )
        (root / "words").mkdir()
        (root / "words" / "nouns.txt").write_text("alpha\nbeta\n", encoding="utf-8")

    def test_import_zip_round_trip(self, tmp_path: Path) -> None:
        pack_dir = tmp_path / "mini"
        self._write_minimal_pack(pack_dir)
        zip_path = tmp_path / "mini.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.write(pack_dir / "pack.yaml", "pack.yaml")
            archive.write(pack_dir / "words" / "nouns.txt", "words/nouns.txt")

        manager = PackManager(user_packs_dir=tmp_path / "user-packs")
        info = manager.import_zip(zip_path)
        assert info.manifest.id == "test.mini"
        assert (info.path / "pack.yaml").is_file()
        bank = ChaffBank.load(info.path)
        assert bank.words("nouns") == ("alpha", "beta")

    def test_import_zip_rejects_zip_slip(self, tmp_path: Path) -> None:
        evil = tmp_path / "evil.zip"
        with zipfile.ZipFile(evil, "w") as archive:
            archive.writestr("../escape.txt", "boom")
        manager = PackManager(user_packs_dir=tmp_path / "user-packs")
        with pytest.raises(PackError, match=r"escape|unsafe|traversal"):
            manager.import_zip(evil)

    def test_import_zip_rejects_absolute_paths(self, tmp_path: Path) -> None:
        evil = tmp_path / "evil-abs.zip"
        with zipfile.ZipFile(evil, "w") as archive:
            archive.writestr("/etc/pwned.txt", "boom")
        manager = PackManager(user_packs_dir=tmp_path / "user-packs")
        with pytest.raises(PackError):
            manager.import_zip(evil)

    def test_list_packs_includes_default(self, default_bank: ChaffBank, tmp_path: Path) -> None:
        manager = PackManager(user_packs_dir=tmp_path / "user-packs")
        listed = {info.manifest.id for info in manager.list_packs()}
        assert "builtin.en.general" in listed

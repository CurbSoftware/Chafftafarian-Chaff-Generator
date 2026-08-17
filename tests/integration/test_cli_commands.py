"""CLI coverage for ``chaff inspect`` and ``chaff packs`` (spec section 53)."""

from __future__ import annotations

from pathlib import Path

from tests.integration.test_verification import _generate
from typer.testing import CliRunner

from chaff_generator.cli.app import app
from chaff_generator.content.bank import default_pack_path

runner = CliRunner()


class TestInspectCommand:
    def test_inspect_run_directory(self, tmp_path: Path) -> None:
        result = _generate(tmp_path, 1 << 20)
        outcome = runner.invoke(app, ["inspect", str(result.run_root)])
        assert outcome.exit_code == 0
        assert result.run_root.name in outcome.output
        assert "Seed" in outcome.output
        assert "Metadata check" in outcome.output
        assert "INTACT" in outcome.output

    def test_inspect_parent_lists_runs(self, tmp_path: Path) -> None:
        result = _generate(tmp_path, 1 << 20)
        outcome = runner.invoke(app, ["inspect", str(tmp_path)])
        assert outcome.exit_code == 0
        assert result.run_root.name in outcome.output
        assert "completed" in outcome.output

    def test_inspect_parent_without_runs_fails(self, tmp_path: Path) -> None:
        outcome = runner.invoke(app, ["inspect", str(tmp_path)])
        assert outcome.exit_code == 1
        assert "No chaff runs" in outcome.output

    def test_inspect_missing_path_fails(self, tmp_path: Path) -> None:
        outcome = runner.invoke(app, ["inspect", str(tmp_path / "nope")])
        assert outcome.exit_code == 1
        assert "Not a chaff run" in outcome.output


class TestPacksCommands:
    def test_list_shows_builtin_pack(self) -> None:
        outcome = runner.invoke(app, ["packs", "list"])
        assert outcome.exit_code == 0
        assert "builtin.en.general" in outcome.output

    def test_show_default_pack(self) -> None:
        outcome = runner.invoke(app, ["packs", "show"])
        assert outcome.exit_code == 0
        assert "builtin.en.general" in outcome.output
        assert "Templates :" in outcome.output
        assert "realistic-desktop" in outcome.output

    def test_show_explicit_path(self) -> None:
        outcome = runner.invoke(app, ["packs", "show", str(default_pack_path())])
        assert outcome.exit_code == 0
        assert "builtin.en.general" in outcome.output

    def test_validate_default_pack(self) -> None:
        outcome = runner.invoke(app, ["packs", "validate", str(default_pack_path())])
        assert outcome.exit_code == 0
        assert "Pack is valid." in outcome.output

    def test_validate_rejects_non_pack(self, tmp_path: Path) -> None:
        outcome = runner.invoke(app, ["packs", "validate", str(tmp_path)])
        assert outcome.exit_code == 1
        assert "invalid" in outcome.output

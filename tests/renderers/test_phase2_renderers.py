"""Phase 2 renderer tests: exact-size contract, parser validity, determinism.

Volume discipline (spec section 72): every rendered file here is at most a
few hundred KiB — these are unit tests, not benchmarks.
"""

from __future__ import annotations

import csv
import json
import random

import pytest

from chaff_generator.content import builders
from chaff_generator.content.context import RenderContext
from chaff_generator.content.template_engine import ChaffTemplateEngine
from chaff_generator.core.hashing import hash_file
from chaff_generator.renderers import build_registry


@pytest.fixture()
def registry():
    return build_registry()


@pytest.fixture()
def world_bank_world(default_bank, world):  # type: ignore[no-untyped-def]
    return default_bank, world


def make_context(world_bank_world, seed: int, desired: int, template_id=None):  # type: ignore[no-untyped-def]
    bank, world = world_bank_world
    rng = random.Random(seed)
    engine = ChaffTemplateEngine(world=world, bank=bank, rng=rng)
    return RenderContext(
        rng=rng,
        world=world,
        bank=bank,
        template_engine=engine,
        desired_size=desired,
        run_id="test",
        app_version="0.1.0",
        template_id=template_id,
    )


class TestExactSizeContract:
    @pytest.mark.parametrize("desired", [16, 512, 4096, 90_000])
    def test_txt_lands_exactly(self, world_bank_world, registry, tmp_path, desired):
        ctx = make_context(world_bank_world, seed=7, desired=desired)
        dest = tmp_path / "exact.txt.chaff-partial"
        result = registry.get("txt").render(None, dest, ctx)
        assert result.size == desired
        assert dest.stat().st_size == desired
        assert result.sha256 == hash_file(dest)
        assert dest.read_bytes().decode("utf-8")  # valid UTF-8 despite the cut

    @pytest.mark.parametrize("desired", [64, 2048, 33_333])
    def test_log_lands_exactly(self, world_bank_world, registry, tmp_path, desired):
        ctx = make_context(world_bank_world, seed=8, desired=desired)
        dest = tmp_path / "exact.log.chaff-partial"
        result = registry.get("log").render(None, dest, ctx)
        assert result.size == desired
        assert result.sha256 == hash_file(dest)

    def test_txt_multibyte_boundary_cut_is_valid_utf8(self, world_bank_world, registry, tmp_path):
        # 100_003 lands mid-paragraph; the padding path must not split a char.
        ctx = make_context(world_bank_world, seed=9, desired=100_003)
        dest = tmp_path / "cut.txt.chaff-partial"
        registry.get("txt").render(None, dest, ctx)
        dest.read_text(encoding="utf-8")  # raises if a codepoint was split


class TestParserValidity:
    def test_csv_parses(self, world_bank_world, registry, tmp_path):
        bank, _ = world_bank_world
        template = bank.templates().require("tabular.asset_inventory")
        ctx = make_context(world_bank_world, seed=11, desired=64_000, template_id=template.id)
        doc = builders.build_tabular_document(template, ctx)
        dest = tmp_path / "out.csv"
        registry.get("csv").render(doc, dest, ctx)
        with dest.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        assert len(rows) >= 50
        assert all(len(row) == len(rows[0]) for row in rows)
        assert b"\r" not in dest.read_bytes()  # LF newlines on every OS

    def test_json_parses(self, world_bank_world, registry, tmp_path):
        bank, _ = world_bank_world
        template = bank.templates().require("record.system_log")
        ctx = make_context(world_bank_world, seed=12, desired=64_000, template_id=template.id)
        doc = builders.build_record_collection(template, ctx)
        dest = tmp_path / "out.json"
        registry.get("json").render(doc, dest, ctx)
        data = json.loads(dest.read_text(encoding="utf-8"))
        assert isinstance(data, list) and len(data) >= 50
        assert all(isinstance(item, dict) for item in data)

    def test_xml_parses(self, world_bank_world, registry, tmp_path):
        import xml.etree.ElementTree as ET

        bank, _ = world_bank_world
        template = bank.templates().require("record.hr_record")
        ctx = make_context(world_bank_world, seed=13, desired=64_000, template_id=template.id)
        doc = builders.build_record_collection(template, ctx)
        dest = tmp_path / "out.xml"
        registry.get("json")  # registry warms
        registry.get("xml").render(doc, dest, ctx)
        root = ET.parse(dest).getroot()
        assert root.tag == "records"
        assert len(root.findall("record")) >= 10

    def test_html_is_well_formed(self, world_bank_world, registry, tmp_path):
        bank, _ = world_bank_world
        template = bank.templates().require("prose.quarterly_summary")
        ctx = make_context(world_bank_world, seed=14, desired=32_000, template_id=template.id)
        doc = builders.build_prose_document(template, ctx)
        dest = tmp_path / "out.html"
        registry.get("html").render(doc, dest, ctx)
        text = dest.read_text(encoding="utf-8")
        assert text.startswith("<!DOCTYPE html>")
        assert text.rstrip().endswith("</html>")
        assert "&lt;" in text or "<p>" in text  # content present, escaped where needed

    def test_md_structure(self, world_bank_world, registry, tmp_path):
        bank, _ = world_bank_world
        template = bank.templates().require("prose.meeting_minutes")
        ctx = make_context(world_bank_world, seed=15, desired=16_000, template_id=template.id)
        doc = builders.build_prose_document(template, ctx)
        dest = tmp_path / "out.md"
        registry.get("md").render(doc, dest, ctx)
        text = dest.read_text(encoding="utf-8")
        assert text.startswith("# ")
        assert "## " in text

    def test_log_lines_have_timestamps(self, world_bank_world, registry, tmp_path):
        ctx = make_context(world_bank_world, seed=16, desired=8_000)
        dest = tmp_path / "out.log"
        registry.get("log").render(None, dest, ctx)
        lines = dest.read_text(encoding="utf-8").splitlines()
        assert lines
        for line in lines[:-1]:  # the exact-size cut may truncate the final line
            assert line[4] == "-" and line[10] == "T"  # ISO timestamp prefix
            assert " [" in line and "] " in line

    def test_dev_python_compiles(self, world_bank_world, registry, tmp_path):
        ctx = make_context(world_bank_world, seed=17, desired=4_000)
        ctx.extra["final_suffix"] = "py"
        ctx.extra["final_stem"] = "demo"
        dest = tmp_path / "demo.py.chaff-partial"
        registry.get("dev").render(None, dest, ctx)
        compile(dest.read_text(encoding="utf-8"), "demo.py", "exec")

    def test_dev_dockerfile_detected_by_stem(self, world_bank_world, registry, tmp_path):
        ctx = make_context(world_bank_world, seed=18, desired=2_000)
        ctx.extra["final_stem"] = "Dockerfile"
        dest = tmp_path / "Dockerfile.chaff-partial"
        registry.get("dev").render(None, dest, ctx)
        text = dest.read_text(encoding="utf-8")
        assert text.startswith("#")
        assert "FROM " in text

    def test_no_leftover_jinja_in_output(self, world_bank_world, registry, tmp_path):
        bank, _ = world_bank_world
        for rid, template_id in (
            ("txt", "prose.proposal"),
            ("md", "prose.technical_report"),
            ("html", "prose.letter"),
            ("csv", "tabular.timesheet"),
            ("json", "record.access_log"),
            ("xml", "record.ticket_history"),
        ):
            template = bank.templates().require(template_id)
            ctx = make_context(world_bank_world, seed=19 + len(rid), desired=32_000)
            builder = {
                "prose": builders.build_prose_document,
                "tabular": builders.build_tabular_document,
                "record": builders.build_record_collection,
            }[template.kind]
            doc = builder(template, ctx)
            dest = tmp_path / f"leftover-{rid}.{rid}"
            registry.get(rid).render(doc, dest, ctx)
            assert "{{" not in dest.read_text(encoding="utf-8"), f"unrendered Jinja in {rid}"
            assert "{%" not in dest.read_text(encoding="utf-8"), f"unrendered tag in {rid}"


class TestDeterminism:
    def test_same_seed_same_bytes_txt_log(self, world_bank_world, registry, tmp_path):
        for rid in ("txt", "log", "csv", "json", "xml", "md", "html"):
            first = tmp_path / f"a-{rid}"
            second = tmp_path / f"b-{rid}"
            ctx_a = make_context(world_bank_world, seed=481_925, desired=24_000)
            ctx_b = make_context(world_bank_world, seed=481_925, desired=24_000)
            registry.get(rid).render(None, first, ctx_a)
            registry.get(rid).render(None, second, ctx_b)
            assert first.read_bytes() == second.read_bytes(), f"{rid} not byte-identical"

    def test_different_seed_different_bytes(self, world_bank_world, registry, tmp_path):
        first = tmp_path / "seed-a.txt"
        second = tmp_path / "seed-b.txt"
        registry.get("txt").render(None, first, make_context(world_bank_world, 1, 8_000))
        registry.get("txt").render(None, second, make_context(world_bank_world, 2, 8_000))
        assert first.read_bytes() != second.read_bytes()


class TestUtf8BoundaryHelper:
    def test_prefix_cuts_on_boundary(self):
        from chaff_generator.renderers.textutil import utf8_prefix

        data = "aé漢字z".encode()
        # Never returns a length that splits a codepoint.
        for limit in range(1, len(data)):
            cut = utf8_prefix(data, limit)
            chunk = data[:cut]
            chunk.decode("utf-8")  # raises if split
        assert utf8_prefix(data, len(data)) == len(data)

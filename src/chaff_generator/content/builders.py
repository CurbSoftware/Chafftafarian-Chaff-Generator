"""Builders convert pack templates into semantic documents (spec section 19).

A template's body is plain data with Jinja strings; builders render every
string through the file's sandboxed engine and produce the typed semantic
models the renderers consume. Size-aware builders (tabular, record) use the
file's ``desired_size`` to decide how many rows to emit.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

from chaff_generator.content import generators as gen
from chaff_generator.renderers.documents import (
    BulletList,
    BulletSlide,
    NumberedList,
    PageBreak,
    Paragraph,
    PresentationDocument,
    ProseDocument,
    Quote,
    RecordCollection,
    Section,
    SectionSlide,
    Sheet,
    Slide,
    Table,
    TableSlide,
    TabularDocument,
    TitleSlide,
)

if TYPE_CHECKING:
    from chaff_generator.content.context import RenderContext
    from chaff_generator.templates.models import TemplateDef

#: Rough bytes per rendered tabular row used to size row counts.
_ROW_BYTES = 64

#: Upper bound on materialized rows: keeps memory flat for large targets.
#: Renderers that only approximate size (csv/json/xml) stop here; exact-size
#: landing is the job of the txt/log/payload finalizers.
MAX_MATERIALIZE_ROWS = 20_000


def _render(context: RenderContext, source: str) -> str:
    return context.template_engine.render_string(source)


def filler_paragraph(context: RenderContext, sentences: int = 3) -> str:
    """Extra prose for size top-up; category matched to the template domain."""
    categories = ("business", "technical", "finance", "support")
    category = categories[context.rng.randrange(len(categories))]
    return context.template_engine.render_string(f"{{{{ paragraph('{category}', {sentences}) }}}}")


def build_prose_document(template: TemplateDef, context: RenderContext) -> ProseDocument:
    body = template.body
    title = _render(context, str(body.get("title", "Document")))
    author = _render(context, str(body.get("author", "")))
    created = _doc_date(context)

    sections: list[Section] = []
    for raw_section in body.get("sections", []):
        heading = raw_section.get("heading")
        section = Section(
            heading=_render(context, str(heading)) if heading else None,
        )
        for key, value in raw_section.items():
            if key == "heading":
                continue
            if key == "paragraphs":
                section.blocks.extend(Paragraph(_render(context, str(text))) for text in value)
            elif key == "bullets":
                section.blocks.append(BulletList([_render(context, str(item)) for item in value]))
            elif key == "numbered":
                section.blocks.append(NumberedList([_render(context, str(item)) for item in value]))
            elif key == "quote":
                section.blocks.append(Quote(_render(context, str(value))))
            elif key == "page_break":
                section.blocks.append(PageBreak())
            elif key == "table":
                table = value
                section.blocks.append(
                    Table(
                        columns=[_render(context, str(c)) for c in table["columns"]],
                        rows=[
                            [_render(context, str(cell)) for cell in row] for row in table["rows"]
                        ],
                    )
                )
        sections.append(section)

    return ProseDocument(
        title=title,
        author=author,
        created_at=created,
        sections=sections,
        metadata={"template": template.id},
    )


def build_tabular_document(template: TemplateDef, context: RenderContext) -> TabularDocument:
    body = template.body
    title = _render(context, str(body.get("sheet_title", template.id)))
    columns = [_render(context, str(c)) for c in body["columns"]]

    row_templates: list[list[str]] = [
        [str(cell) for cell in row] for row in (body.get("rows") or [])
    ]
    if not row_templates:
        row_templates = [[str(column) for column in columns]]

    target_rows = (
        max(1, context.desired_size // _ROW_BYTES) if context.desired_size else len(row_templates)
    )
    target_rows = min(max(target_rows, len(row_templates)), MAX_MATERIALIZE_ROWS)
    rows: list[list[Any]] = []
    while len(rows) < target_rows:
        pattern = row_templates[len(rows) % len(row_templates)]
        rows.append([_render(context, cell) for cell in pattern])

    sheet = Sheet(name=title[:31], columns=columns, rows=rows)
    return TabularDocument(
        title=title,
        author=context.world.primary_user.full_name,
        sheets=[sheet],
    )


def build_presentation_document(
    template: TemplateDef, context: RenderContext
) -> PresentationDocument:
    body = template.body
    title = _render(context, str(body.get("title", template.id)))
    subtitle = _render(context, str(body.get("subtitle", "")))

    slides: list[Slide] = []
    for raw_slide in body.get("slides", []):
        kind = str(raw_slide.get("kind", "bullets"))
        if kind == "title":
            slides.append(
                TitleSlide(
                    title=_render(context, str(raw_slide.get("heading", title))),
                    subtitle=_render(context, str(raw_slide.get("note", subtitle))),
                )
            )
        elif kind == "section":
            slides.append(SectionSlide(title=_render(context, str(raw_slide.get("heading", "")))))
        elif kind == "table":
            slides.append(
                TableSlide(
                    title=_render(context, str(raw_slide.get("heading", ""))),
                    columns=[_render(context, str(c)) for c in raw_slide.get("columns", [])],
                    rows=[
                        [_render(context, str(cell)) for cell in row]
                        for row in raw_slide.get("rows", [])
                    ],
                )
            )
        else:  # bullets (the default)
            slides.append(
                BulletSlide(
                    title=_render(context, str(raw_slide.get("heading", ""))),
                    bullets=[_render(context, str(item)) for item in raw_slide.get("bullets", [])],
                )
            )

    return PresentationDocument(
        title=title,
        author=context.world.primary_user.full_name,
        slides=slides,
    )


def build_record_collection(template: TemplateDef, context: RenderContext) -> RecordCollection:
    body = template.body
    record_type = str(body.get("record_type", template.id.replace("record.", "")))
    columns = [str(c) for c in body["columns"]]
    count = int(body.get("row_count", 40))
    if context.desired_size:
        count = max(1, min(count, context.desired_size // _ROW_BYTES))
    count = min(count, MAX_MATERIALIZE_ROWS)
    records = [_record_row(record_type, columns, context, index) for index in range(count)]
    return RecordCollection(record_type=record_type, records=records)


def _doc_date(context: RenderContext) -> date:
    timeline = context.world.timeline
    if timeline is not None:
        return timeline.draw_between(context.rng)
    return date(2025, 6, 15)


def _iso_datetime(context: RenderContext, day_offset: int = 0) -> str:
    day = _doc_date(context) - timedelta(days=day_offset)
    moment = time(
        context.rng.randrange(0, 24),
        context.rng.randrange(0, 60),
        context.rng.randrange(0, 60),
    )
    return datetime.combine(day, moment).isoformat(timespec="seconds")


def _record_row(
    record_type: str, columns: list[str], context: RenderContext, index: int
) -> dict[str, Any]:
    """Generate one plausible record row for the given record type."""
    rng = context.rng
    world = context.world
    if record_type == "system_log":
        levels = ("INFO", "INFO", "INFO", "WARN", "DEBUG", "ERROR")
        source = ("service", "gateway", "worker", "scheduler", "api")
        return {
            "timestamp": _iso_datetime(context, index // 50),
            "level": gen.pick(rng, levels),
            "service": f"{gen.pick(rng, source)}-{rng.randrange(1, 9)}",
            "message": context.template_engine.render_string("{{ sentence('technical') }}"),
            "trace_id": f"tr{rng.getrandbits(48):012x}",
        }
    if record_type == "hr_record":
        person = gen.pick(rng, world.employees)
        return {
            "employee_id": person.id.upper(),
            "full_name": person.full_name,
            "department": person.department,
            "job_title": person.job_title,
            "hire_date": person.hire_date.isoformat(),
            "email": person.email,
        }
    if record_type == "access_log":
        person = world.any_person(rng)
        doors = ("lobby-north", "lobby-south", "dock", "server-room", "floor-2", "floor-3")
        results = ("granted", "granted", "granted", "denied")
        return {
            "timestamp": _iso_datetime(context, index // 30),
            "badge_id": f"BDG{rng.randrange(10000, 99999)}",
            "person": person.full_name,
            "door": gen.pick(rng, doors),
            "result": gen.pick(rng, results),
        }
    if record_type == "ticket_history":
        reporter = gen.pick(rng, (*world.employees, *world.contacts))
        assignee = world.any_person(rng)
        statuses = ("open", "in progress", "pending user", "resolved", "closed")
        status = gen.pick(rng, statuses)
        opened = _iso_datetime(context, index // 5)
        closed = _iso_datetime(context, 0) if status in ("resolved", "closed") else ""
        return {
            "ticket": f"TKT-{rng.randrange(10000, 99999)}",
            "opened": opened,
            "reporter": reporter.full_name,
            "assignee": assignee.full_name,
            "category": gen.pick(rng, ("access", "hardware", "software", "network", "account")),
            "status": status,
            "closed": closed,
        }
    if record_type == "equipment_register":
        holder = world.any_person(rng)
        due = _doc_date(context) + timedelta(days=rng.randrange(1, 60))
        return {
            "item": gen.pick(rng, context.bank.words("products")),
            "asset_tag": f"AST-{rng.randrange(1000, 9999)}",
            "checked_out": _iso_datetime(context, rng.randrange(1, 30)),
            "holder": holder.full_name,
            "due_back": due.isoformat(),
            "returned": "" if rng.random() < 0.4 else _iso_datetime(context, 0),
        }
    if record_type == "policy_acknowledgement":
        person = gen.pick(rng, (*world.employees, *world.contacts))
        return {
            "policy": context.template_engine.render_string("{{ word('topics') | title }} Policy"),
            "version": f"{rng.randrange(1, 4)}.{rng.randrange(0, 9)}",
            "employee": person.full_name,
            "department": person.department,
            "signed_on": _iso_datetime(context, rng.randrange(1, 120)),
        }
    # Generic fallback: fill each column with a plausible value.
    return {column: f"{column}-{index}-{rng.randrange(1000, 9999)}" for column in columns}

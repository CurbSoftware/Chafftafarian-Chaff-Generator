"""Shared row-source resolution for csv/json/xml record renderers.

Each of those formats renders the same underlying data — either a
:class:`TabularDocument` (columns + rows) from a tabular template or a
:class:`RecordCollection` (dict rows) from a record template. When the
planner picks one of these formats with no matching template, a synthetic
order-log table is generated from the world so the renderer never fails for
lack of a document.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from chaff_generator.renderers.documents import RecordCollection, TabularDocument

if TYPE_CHECKING:
    from chaff_generator.content.context import RenderContext
    from chaff_generator.renderers.documents import SemanticDocument


def columnar_records(
    document: SemanticDocument | None, context: RenderContext
) -> tuple[str, list[str], Iterator[list[str]]]:
    """Resolve ``document`` to ``(title, columns, row_iterator)``.

    Rows are yielded lazily so large files stream; dict records are ordered
    by the first record's keys.
    """
    if isinstance(document, TabularDocument) and document.sheets:
        sheet = document.sheets[0]
        return document.title, list(sheet.columns), iter(sheet.rows)
    if isinstance(document, RecordCollection) and document.records:
        keys = list(document.records[0].keys())
        return (
            document.record_type,
            keys,
            ([record[key] for key in keys] for record in document.records),
        )
    return _synthetic_rows(context)


def object_records(
    document: SemanticDocument | None, context: RenderContext
) -> tuple[str, Iterator[dict[str, Any]]]:
    """Resolve ``document`` to ``(title, dict_row_iterator)`` for json."""
    if isinstance(document, TabularDocument) and document.sheets:
        sheet = document.sheets[0]
        return document.title, (dict(zip(sheet.columns, row, strict=False)) for row in sheet.rows)
    if isinstance(document, RecordCollection) and document.records:
        return document.record_type, iter(document.records)
    _title, _columns, rows = _synthetic_rows(context)
    return _title, (dict(zip(_columns, row, strict=False)) for row in rows)


def _synthetic_rows(context: RenderContext) -> tuple[str, list[str], Iterator[list[str]]]:
    """Fallback order-log table generated straight from the world."""

    def generate() -> Iterator[list[str]]:
        while True:
            yield [
                context.template_engine.render_string("{{ uuid() }}"),
                context.template_engine.render_string("{{ word('products') }}"),
                str(context.rng.randrange(1, 20)),
                str(context.rng.randrange(10, 900)),
            ]

    return (
        "order_log",
        ["order_id", "item", "quantity", "unit_price"],
        generate(),
    )

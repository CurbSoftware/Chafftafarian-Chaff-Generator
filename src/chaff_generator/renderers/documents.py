"""Semantic document models (spec section 19).

Renderers never invent their own content: templates produce one of these
intermediate documents, and each format renderer emits the same document in
its own file format. This prevents five independent copies of every report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class Heading:
    text: str
    level: int = 1


@dataclass
class Paragraph:
    text: str


@dataclass
class BulletList:
    items: list[str]


@dataclass
class NumberedList:
    items: list[str]


@dataclass
class Table:
    columns: list[str]
    rows: list[list[str]]


@dataclass
class Quote:
    text: str


@dataclass
class PageBreak:
    pass


Block = Heading | Paragraph | BulletList | NumberedList | Table | Quote | PageBreak


@dataclass
class Section:
    heading: str | None = None
    blocks: list[Block] = field(default_factory=list)


@dataclass
class ProseDocument:
    title: str
    author: str
    created_at: date
    sections: list[Section] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class EmailAttachment:
    filename: str
    mime_type: str
    content: bytes


@dataclass
class EmailDocument:
    subject: str
    from_name: str
    from_email: str
    to_name: str
    to_email: str
    sent_at: datetime
    body_plain: str
    cc: list[tuple[str, str]] = field(default_factory=list)
    body_html: str | None = None
    message_id: str = ""
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)
    attachments: list[EmailAttachment] = field(default_factory=list)


@dataclass
class Sheet:
    name: str
    columns: list[str]
    rows: list[list[Any]]
    currency_columns: set[int] = field(default_factory=set)
    date_columns: set[int] = field(default_factory=set)
    total_row: bool = False


@dataclass
class TabularDocument:
    title: str
    author: str
    sheets: list[Sheet] = field(default_factory=list)


@dataclass
class TitleSlide:
    title: str
    subtitle: str


@dataclass
class SectionSlide:
    title: str


@dataclass
class BulletSlide:
    title: str
    bullets: list[str]


@dataclass
class TableSlide:
    title: str
    columns: list[str]
    rows: list[list[str]]


Slide = TitleSlide | SectionSlide | BulletSlide | TableSlide


@dataclass
class PresentationDocument:
    title: str
    author: str
    slides: list[Slide] = field(default_factory=list)


@dataclass
class RecordCollection:
    record_type: str
    records: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CalendarEvent:
    uid: str
    summary: str
    start: datetime
    end: datetime
    location: str = ""
    organizer_email: str = ""


@dataclass
class CalendarDocument:
    events: list[CalendarEvent] = field(default_factory=list)


@dataclass
class ContactRecord:
    full_name: str
    email: str
    phone: str
    organization: str = ""
    title: str = ""
    city: str = ""


@dataclass
class ContactDocument:
    contacts: list[ContactRecord] = field(default_factory=list)


SemanticDocument = (
    ProseDocument
    | EmailDocument
    | TabularDocument
    | PresentationDocument
    | RecordCollection
    | CalendarDocument
    | ContactDocument
)

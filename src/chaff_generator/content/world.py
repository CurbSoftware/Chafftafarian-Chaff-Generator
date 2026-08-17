"""The synthetic generation universe (spec sections 18, 64).

Every run builds one coherent world — an organization, its people, projects,
products, meetings, and invoices — that is reused across all generated
documents so files appear to belong to the same fictional environment.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field, replace
from datetime import date, timedelta

from chaff_generator.content import generators as gen
from chaff_generator.content.bank import ChaffBank
from chaff_generator.content.entities import (
    Company,
    Invoice,
    InvoiceLine,
    Meeting,
    Organization,
    Person,
    Product,
    Project,
)
from chaff_generator.core.models import DateRange, GenerationConfig


def world_seed(master_seed: int) -> int:
    """Domain-separated seed for world construction."""
    digest = hashlib.sha256(f"chaff-world-seed:v1:{master_seed}".encode()).digest()
    return int.from_bytes(digest[:16], "big")


class Timeline:
    """Helpers that keep generated dates chronologically consistent (§64)."""

    def __init__(self, rng: random.Random, date_range: DateRange) -> None:
        self._rng = rng
        self._range = date_range

    def between(self) -> date:
        return gen.date_between(self._rng, self._range.start, self._range.end)

    def draw_between(self, rng: random.Random) -> date:
        """Draw a date in range using the *caller's* RNG.

        Renderers must use this, not :meth:`between`: the timeline's own RNG
        is shared world state, so consuming it during rendering would make a
        file's bytes depend on every file rendered before it (spec section 11
        requires a file to be reproducible from its seed alone).
        """
        return gen.date_between(rng, self._range.start, self._range.end)

    def after(self, anchor: date, min_days: int = 1, max_days: int = 45) -> date:
        """A date after ``anchor``; clamped into the configured range."""
        candidate = gen.date_after(self._rng, anchor, min_days, max_days)
        latest = self._range.end
        return min(candidate, latest) if candidate > latest else candidate

    def before(self, anchor: date, min_days: int = 1, max_days: int = 90) -> date:
        """A date before ``anchor``; clamped into the configured range."""
        candidate = anchor - timedelta(days=self._rng.randrange(min_days, max_days + 1))
        return max(candidate, self._range.start)


@dataclass
class GenerationWorld:
    primary_user: Person
    organization: Organization
    employees: list[Person] = field(default_factory=list)
    contacts: list[Person] = field(default_factory=list)
    clients: list[Company] = field(default_factory=list)
    vendors: list[Company] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    products: list[Product] = field(default_factory=list)
    meetings: list[Meeting] = field(default_factory=list)
    invoices: list[Invoice] = field(default_factory=list)
    date_range: DateRange | None = None
    topics: list[str] = field(default_factory=list)
    timeline: Timeline | None = None

    def person_by_id(self, person_id: str) -> Person | None:
        for person in [self.primary_user, *self.employees, *self.contacts]:
            if person.id == person_id:
                return person
        return None

    def project_by_id(self, project_id: str) -> Project | None:
        return next((project for project in self.projects if project.id == project_id), None)

    def any_person(self, rng: random.Random) -> Person:
        """The primary user or any employee — used for document authorship."""
        pool = [self.primary_user, *self.employees]
        return gen.pick(rng, pool)

    def any_project(self, rng: random.Random) -> Project:
        return gen.pick(rng, self.projects)


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _make_person(rng: random.Random, bank: ChaffBank, timeline: Timeline, index: int) -> Person:
    male = bank.entity_lines("first_names_male")
    female = bank.entity_lines("first_names_female")
    last = bank.entity_lines("last_names")
    first = gen.pick(rng, (*male, *female))
    last_name = gen.pick(rng, last)
    domain = "example.com"
    email = gen.make_email(f"{first}.{last_name}".lower(), domain)
    return Person(
        id=f"p{index:03d}",
        first_name=first,
        last_name=last_name,
        email=email,
        phone=gen.make_phone(rng),
        job_title=gen.pick(rng, bank.entity_lines("job_titles")),
        department=gen.pick(rng, bank.entity_lines("departments")),
        hire_date=timeline.between(),
    )


def _make_external_companies(
    rng: random.Random, bank: ChaffBank, timeline: Timeline, count: int, kind: str, start_index: int
) -> list[Company]:
    companies: list[Company] = []
    for offset in range(count):
        index = start_index + offset
        contact = _make_person(rng, bank, timeline, 900 + index)
        companies.append(
            Company(
                id=f"c{index:03d}",
                name=f"{gen.make_company_name(rng, bank)}",
                contact_id=contact.id,
                city=gen.make_city(rng, bank),
                kind=kind,
            )
        )
    return companies


def _make_projects(
    rng: random.Random,
    bank: ChaffBank,
    timeline: Timeline,
    people: list[Person],
    count: int,
) -> list[Project]:
    projects: list[Project] = []
    statuses = ("active", "active", "planning", "completed", "on hold")
    for index in range(count):
        start = timeline.between()
        status = gen.pick(rng, statuses)
        end = timeline.after(start, 30, 400) if status == "completed" else None
        manager = gen.pick(rng, people)
        projects.append(
            Project(
                id=f"prj{index:02d}",
                name=gen.make_project_name(rng, bank),
                code=f"{gen.pick(rng, bank.words('nouns'))[:2].upper()}-{rng.randrange(100, 999)}",
                manager_id=manager.id,
                start_date=start,
                end_date=end,
                budget=rng.randrange(10_000, 950_000),
                status=status,
                department=manager.department,
            )
        )
    return projects


def _make_products(rng: random.Random, bank: ChaffBank, count: int) -> list[Product]:
    raw = bank.entity_json("products")
    rows = raw if isinstance(raw, list) else []
    products: list[Product] = []
    for index in range(count):
        if rows:
            row = rows[(index + rng.randrange(0, len(rows))) % len(rows)]
            name = str(row.get("name", f"Component {index}"))
            category = str(row.get("category", "general"))
            price = float(row.get("unit_price", rng.randrange(20, 2000)))
        else:
            adjective = gen.pick(rng, bank.words("adjectives")).title()
            noun = gen.pick(rng, bank.words("nouns")).title()
            name = f"{adjective} {noun}"
            category = "general"
            price = float(rng.randrange(20, 2000))
        products.append(
            Product(
                sku=f"SKU-{rng.randrange(10000, 99999)}",
                name=name,
                category=category,
                unit_price=round(price, 2),
            )
        )
    return products


def _make_meetings(
    rng: random.Random,
    bank: ChaffBank,
    timeline: Timeline,
    people: list[Person],
    projects: list[Project],
    count: int,
) -> list[Meeting]:
    meetings: list[Meeting] = []
    action_pool = bank.phrases("meeting_actions") or ("Follow up on open items",)
    for index in range(count):
        when = timeline.between()
        attendees = rng.sample(people, k=min(len(people), rng.randrange(3, 7)))
        topic = (
            f"{gen.pick(rng, projects).name} review"
            if projects
            else gen.pick(rng, bank.words("topics")).title()
        )
        meetings.append(
            Meeting(
                id=f"mtg{index:02d}",
                date=when,
                attendee_ids=tuple(person.id for person in attendees),
                topic=topic,
                action_items=tuple(gen.pick(rng, action_pool) for _ in range(rng.randrange(2, 5))),
            )
        )
    return meetings


def _make_invoices(
    rng: random.Random,
    bank: ChaffBank,
    timeline: Timeline,
    clients: list[Company],
    products: list[Product],
    count: int,
) -> list[Invoice]:
    invoices: list[Invoice] = []
    for _index in range(count):
        issued = timeline.between()
        due = timeline.after(issued, 14, 60)
        client = gen.pick(rng, clients) if clients else None
        lines = tuple(
            InvoiceLine(
                description=gen.pick(rng, products).name if products else "Professional services",
                quantity=rng.randrange(1, 12),
                unit_price=float(rng.randrange(25, 900)),
            )
            for _ in range(rng.randrange(1, 5))
        )
        invoices.append(
            Invoice(
                number=f"{rng.randrange(10000, 99999)}",
                issued=issued,
                due=due,
                client=client.name if client else gen.make_company_name(rng, bank),
                lines=lines,
            )
        )
    return invoices


def build_world(
    master_seed: int, config: GenerationConfig, bank: ChaffBank, *, estimated_files: int = 250
) -> GenerationWorld:
    """Build the deterministic generation universe for a run.

    Entity counts scale with the planned volume so small runs stay light and
    very large runs stay rich (spec section 18).
    """
    rng = random.Random(world_seed(master_seed))
    timeline = Timeline(rng, config.date_range)

    person_count = _clamp(estimated_files // 25, 8, 60)
    project_count = _clamp(estimated_files // 80, 3, 8)
    client_count = _clamp(estimated_files // 60, 2, 12)
    vendor_count = _clamp(estimated_files // 120, 1, 6)
    product_count = _clamp(estimated_files // 40, 6, 40)
    meeting_count = _clamp(estimated_files // 30, 4, 30)
    invoice_count = _clamp(estimated_files // 50, 3, 24)
    contact_count = _clamp(estimated_files // 50, 4, 30)

    organization = Organization(
        name=gen.make_company_name(rng, bank),
        legal_suffix=gen.pick(rng, ("LLC", "Inc.", "Group", "Holdings")),
        domain="northstar.example",
        departments=tuple(bank.entity_lines("departments")[:8]),
        hq_city=gen.make_city(rng, bank),
    )

    employees = [_make_person(rng, bank, timeline, index) for index in range(person_count)]
    primary_user = employees[0]

    # Organization email domain for internal staff (still non-routable, §17).
    primary_user = replace(
        primary_user,
        email=gen.make_email(
            f"{primary_user.first_name}.{primary_user.last_name}".lower(),
            organization.domain,
        ),
    )
    employees[0] = primary_user

    contacts = [_make_person(rng, bank, timeline, 500 + index) for index in range(contact_count)]
    clients = _make_external_companies(rng, bank, timeline, client_count, "client", 100)
    vendors = _make_external_companies(rng, bank, timeline, vendor_count, "vendor", 200)
    projects = _make_projects(rng, bank, timeline, employees, project_count)
    products = _make_products(rng, bank, product_count)
    meetings = _make_meetings(rng, bank, timeline, employees, projects, meeting_count)
    invoices = _make_invoices(rng, bank, timeline, clients, products, invoice_count)

    return GenerationWorld(
        primary_user=primary_user,
        organization=organization,
        employees=employees,
        contacts=contacts,
        clients=clients,
        vendors=vendors,
        projects=projects,
        products=products,
        meetings=meetings,
        invoices=invoices,
        date_range=config.date_range,
        topics=list(bank.words("topics")),
        timeline=timeline,
    )

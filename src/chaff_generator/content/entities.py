"""Synthetic entity models for the generation world (spec section 18).

Entities are plain dataclasses with precomputed display fields (``full_name``,
``domain``, ...) so templates never need to call methods on them — the Jinja
sandbox only ever sees attributes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Person:
    id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    job_title: str
    department: str
    hire_date: date

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclass(frozen=True)
class Organization:
    name: str
    legal_suffix: str
    domain: str
    departments: tuple[str, ...]
    hq_city: str

    @property
    def legal_name(self) -> str:
        return f"{self.name} {self.legal_suffix}"


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    code: str
    manager_id: str
    start_date: date
    end_date: date | None
    budget: int
    status: str
    department: str


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    category: str
    unit_price: float


@dataclass(frozen=True)
class Meeting:
    id: str
    date: date
    attendee_ids: tuple[str, ...]
    topic: str
    action_items: tuple[str, ...]


@dataclass(frozen=True)
class InvoiceLine:
    description: str
    quantity: int
    unit_price: float

    @property
    def total(self) -> float:
        return round(self.quantity * self.unit_price, 2)


@dataclass(frozen=True)
class Invoice:
    number: str
    issued: date
    due: date
    client: str
    lines: tuple[InvoiceLine, ...] = field(default=())

    @property
    def total(self) -> float:
        return round(sum(line.total for line in self.lines), 2)


@dataclass(frozen=True)
class Company:
    """An external company (client or vendor)."""

    id: str
    name: str
    contact_id: str
    city: str
    kind: str  # "client" or "vendor"

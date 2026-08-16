#!/usr/bin/env python3
"""One-time harvest of legacy prototype data into the default ChaffBank pack.

Converts the flat files that shipped with the original prototype (root ``data/``
directory, largely sourced from the MIT-licensed Sentence-Generator project and
US Census name distributions) into the clean formats used by
``src/chaff_generator/data/default-pack/``.

Run once from the repository root:

    python scripts/harvest_legacy_data.py

The script is kept in the repository for provenance: it documents exactly how
each harvested file was produced. It is not part of the installed package.

Deliberately NOT harvested (synthetic-only policy, spec section 17):
    - bay_area_addresses.csv  (real business names and addresses)
    - PERSON-FAMOUS.vocab     (real people)
    - queries.txt / queries.csv (superseded by the Jinja template vocabulary)
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LEGACY_DATA = REPO_ROOT / "data"
PACK_ROOT = REPO_ROOT / "src" / "chaff_generator" / "data" / "default-pack"

FIRST_NAMES_LIMIT = 600
LAST_NAMES_LIMIT = 1200
US_CITIES_LIMIT = 800
STREET_NAMES_LIMIT = 400


def read_lines(path: Path) -> Iterator[str]:
    """Yield non-empty stripped lines, skipping ``#`` comments."""
    with path.open(encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if line and not line.startswith("#"):
                yield line


def harvest_census_names(source: Path, limit: int) -> list[str]:
    """Take the top ``limit`` names from a Census distribution file.

    Input format: ``NAME  prob  cumulative  rank`` (whitespace-delimited,
    already sorted by frequency/rank). Output is title-cased.
    """
    names: list[str] = []
    for line in read_lines(source):
        name = line.split()[0]
        names.append(name.title())
        if len(names) >= limit:
            break
    return names


def harvest_cities(us_cities: Path, international: Path, limit: int) -> list[dict[str, object]]:
    """Merge US city names and the international cities CSV into cities.json rows."""
    seen: set[str] = set()
    rows: list[dict[str, object]] = []

    for name in read_lines(us_cities):
        if len(rows) >= limit:
            break
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        rows.append({"city": name, "country": "United States", "region": None})

    with international.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = row["city"].casefold()
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "city": row["city"],
                    "country": row["country"],
                    "region": row["region"],
                }
            )
    return rows


def harvest_street_names(source: Path, limit: int) -> list[str]:
    """Take the top ``limit`` street names from the TSV (name<TAB>count, with header)."""
    streets: list[str] = []
    with source.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        next(reader, None)  # skip header row
        for row in reader:
            if not row:
                continue
            streets.append(row[0].strip())
            if len(streets) >= limit:
                break
    return streets


def write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    print(f"wrote {path.relative_to(REPO_ROOT)} ({len(lines)} entries)")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(f"wrote {path.relative_to(REPO_ROOT)}")


def main() -> None:
    if not LEGACY_DATA.is_dir():
        raise SystemExit(f"legacy data directory not found: {LEGACY_DATA}")

    write_lines(
        PACK_ROOT / "entities" / "first_names_male.txt",
        harvest_census_names(LEGACY_DATA / "dist.male.first", FIRST_NAMES_LIMIT),
    )
    write_lines(
        PACK_ROOT / "entities" / "first_names_female.txt",
        harvest_census_names(LEGACY_DATA / "dist.female.first", FIRST_NAMES_LIMIT),
    )
    write_lines(
        PACK_ROOT / "entities" / "last_names.txt",
        harvest_census_names(LEGACY_DATA / "dist.all.last", LAST_NAMES_LIMIT),
    )
    write_lines(
        PACK_ROOT / "entities" / "street_names.txt",
        harvest_street_names(
            LEGACY_DATA / "us_street_name_sorted_top75percent.csv", STREET_NAMES_LIMIT
        ),
    )
    write_json(
        PACK_ROOT / "entities" / "cities.json",
        harvest_cities(
            LEGACY_DATA / "us_cities.csv",
            LEGACY_DATA / "international_cities.csv",
            US_CITIES_LIMIT,
        ),
    )
    # Narrative sentence pool (public-domain prose patterns from the legacy
    # Sentence-Generator data) seeds the personal sentence bank.
    write_lines(
        PACK_ROOT / "sentences" / "personal.txt",
        list(read_lines(LEGACY_DATA / "sentences.txt")),
    )
    # Business email body sentences seed the business sentence bank.
    write_lines(
        PACK_ROOT / "sentences" / "business.txt",
        list(read_lines(LEGACY_DATA / "business_emails.txt")),
    )
    # Technology vocabulary starter.
    write_lines(
        PACK_ROOT / "words" / "technologies.txt",
        list(read_lines(LEGACY_DATA / "TECHNOLOGY.vocab")),
    )


if __name__ == "__main__":
    main()

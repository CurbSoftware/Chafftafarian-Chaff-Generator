# Default Pack Attribution

## Contents overview

All content in this pack is either:

1. Authored specifically for Chaff Generator, or
2. Derived from public-domain / open data sources listed below.

No scraped personal data, customer databases, or real individual identities are
included. Generated identities are assembled synthetically from name-frequency
lists; email addresses use reserved non-routable domains (`example.com`,
`*.example`).

## Sources

### US Census surname and given-name distributions (public domain)

- `entities/first_names_male.txt` — top names from `dist.male.first`
- `entities/first_names_female.txt` — top names from `dist.female.first`
- `entities/last_names.txt` — top surnames from `dist.all.last`

Produced by `scripts/harvest_legacy_data.py` from the Census Bureau name
distribution files shipped with the original prototype. United States Census
Bureau works are in the public domain (17 U.S.C. § 105).

### Legacy Sentence-Generator data (MIT)

- `sentences/personal.txt` — narrative sentence pool (public-domain novel prose
  patterns originally distributed with github.com/HadoopIt/Sentence-Generator,
  MIT licensed)
- `words/technologies.txt` — technology vocabulary starter

### Project-authored

Everything else — word banks, phrase banks, sentence banks, entity lists,
templates, and profiles — was written for Chaff Generator and ships under the
project's MIT license.

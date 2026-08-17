# ChaffBank Packs

A **ChaffBank pack** is a data-only directory that feeds every piece of text
Chaff Generator writes: vocabulary, sentences, entities, document templates,
and generation profiles. Packs contain **no code** — no Python modules are
imported from a pack, so importing an untrusted pack cannot execute anything.

## Layout

```text
my-pack/
├── pack.yaml              # identity: id, name, version, language, …
├── ATTRIBUTION.md         # where the data came from (recommended)
├── words/                 # one word bank per file (.txt, one word per line)
│   ├── nouns.txt
│   ├── technologies.txt
│   └── …
├── phrases/               # short multi-word fragments (.txt)
│   ├── greetings.txt
│   └── closings.txt
├── sentences/             # full sentence pools per domain (.txt)
│   ├── business.txt
│   └── technical.txt
├── entities/              # names, places, org vocabulary
│   ├── first_names_female.txt
│   ├── last_names.txt
│   ├── departments.txt
│   ├── job_titles.txt
│   ├── street_names.txt
│   ├── cities.json
│   └── products.json
├── templates/             # Jinja templates grouped by kind
│   ├── prose/*.yaml
│   ├── email/*.yaml
│   ├── tabular/*.yaml
│   ├── presentation/*.yaml
│   ├── record/*.yaml
│   ├── calendar/*.yaml
│   └── contact/*.yaml
└── profiles/              # per-profile format weights and size ranges
    ├── realistic-desktop.yaml
    └── …
```

Blank lines and `#` comments are ignored in every text bank. `cities.json`
and `products.json` are structured entity tables consumed by the world
builder.

## Banks

- **Word banks** (`words/`) — single tokens, drawn by templates via
  `word('technologies')` and used to build filenames, project names, and
  topical filler.
- **Phrase banks** (`phrases/`) — fragments like greetings, sign-offs, and
  status lines that appear verbatim inside documents.
- **Sentence banks** (`sentences/`) — full sentences grouped by *domain*
  (`business`, `personal`, `technical`, `finance`, `project_updates`,
  `support`). Sentences may contain `{{ }}` variables the renderer fills
  from the run's world. Text-oriented renderers (`.txt`, `.log`, `.md`,
  `.html`) and exact-size streamers draw their prose from these pools.
- **Entity data** (`entities/`) — the raw material for the synthetic world:
  given/family names (frequency-ranked), departments, job titles, street and
  city names, product lines. The world builder (`content/world.py`) assembles
  people, an organization, projects, meetings, and invoices from them. All
  e-mail addresses use reserved, non-routable domains (`@example.com`,
  `@<org>.example`) — generated content never references real individuals or
  routable addresses.
- **Templates** (`templates/`) — the document skeletons, one YAML file per
  template, validated against a per-kind schema (see
  [templates.md](templates.md)).
- **Profiles** (`profiles/`) — named output mixes: which formats appear, how
  often, and in what size ranges (see the profile list below).

## The built-in pack

Chaff Generator ships `builtin.en.general` (47 templates, 6 profiles),
authored for the project with given/family names derived from US Census
Bureau name-frequency data (public domain) — see the pack's
`ATTRIBUTION.md`.

## Managing packs

```bash
chaff packs list                                   # builtin + user packs
chaff packs show [DIR]                             # summarize banks/templates
chaff packs validate DIR                           # schema + render checks
chaff packs import archive.zip [--name my-pack]    # install a ZIP
```

User packs install to the platform data dir (e.g.
`~/.local/share/chaff-generator/packs` on Linux,
`%LOCALAPPDATA%\chaff-generator\packs` on Windows,
`~/Library/Application Support/chaff-generator/packs` on macOS). Exactly one
pack is *active* per run — the GUI's ChaffBank page selects it, and
`chaff generate --config`/API callers load one explicitly.

### ZIP imports

`packs import` extracts a ZIP with path-traversal (zip-slip) protection,
file-count and size limits, and refuses anything containing Python modules or
executable entries. A pack that fails validation can still be imported, but
`chaff packs validate` and the GUI preview will show why it is broken before
you ever generate with it.

### Custom profiles

A *profile* inside a pack describes `format_weights` (how often each
renderer runs), `size_profile` (min/typ/max per format), `content_domains`
(sentence pools to favor), and the directory layout flavor. The built-in set:

| Profile | Character |
| --- | --- |
| `realistic-desktop` | Mixed personal + business documents, deep folders |
| `office-workstation` | Memos, spreadsheets, slides, meeting traffic |
| `personal-computer` | Notes, letters, photos-like text, casual mail |
| `developer-workstation` | Code-ish dev files, logs, tickets, READMEs |
| `storage-test` | Almost entirely `.dat` payload files for volume |
| `balanced` | Even spread across all enabled formats |

Any config option can also be set directly (CLI flags / GUI) without a
profile — profiles are conveniences, not requirements.

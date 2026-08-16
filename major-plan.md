
THIS PROJECT MUST WORK ON ALL STANDARD OPERATING SYSTEMS, WINDOWS, LINUX, and MAC

Yes. I would build **Chaff Generator** as a proper reusable data-generation engine rather than a monolithic Python utility. The desktop application would be the primary interface, but the generation engine, template system, verification system, and cleanup system would all be independent of the UI.

For the implementation stack, **PySide6** is the strongest choice for the desktop UI because it is the official Qt-for-Python binding. ([Qt Documentation][1]) Jinja gives you essentially the `{{ variable }}` syntax you described and provides a sandbox specifically for restricting untrusted templates. ([Jinja Documentation][2]) Typer fits the secondary CLI well and supports multi-command applications. ([Typer][3]) Python's standard library already provides proper MIME/email generation as well as Maildir and mbox support. ([Python documentation][4]) Real Office files can be generated with python-docx, openpyxl, and python-pptx rather than creating fake files with Office extensions. ([Python-docx][5]) Send2Trash provides native Trash/Recycle Bin behavior across platforms, and PyInstaller can produce standalone packaged applications. ([GitHub][6])

One terminology distinction is important. I would **not advertise filling free space with generated files and deleting them as "secure erasure."** NIST's current media-sanitization guidance is SP 800-88 Rev. 2, finalized September 26, 2025. ([NIST Computer Security Resource Center][7]) Flash storage in particular uses mechanisms such as wear levelling that can prevent ordinary filesystem overwrite operations from reaching every physical storage location. ([Canadian Centre for Cyber Security][8]) Chaff can absolutely provide a **Free-Space Fill** mode, but disposal-grade sanitization should remain a separate concern.

The biggest feature I would add to your original concept is the **integrity manifest**. Chaff should record the SHA-256 of every generated file. You can then fill a drive with 500 GB of Chaff, put the drive into service or stress it, and later tell Chaff to verify the entire corpus. It can tell you precisely which files disappeared, changed size, or suffered a hash mismatch. That makes the project considerably more useful than a dummy-file generator.

Here is the complete development prompt I would give a coding agent:

# Chaff Generator — Comprehensive AI Coding Agent Development Prompt

## 1. Your Role

Act as the senior Python software architect and implementation engineer responsible for designing and building a production-quality application called **Chaff Generator**.

Do not treat this as a quick script.

Build it as a modular Python application with:

* a reusable generation engine;
* a desktop graphical interface;
* a command-line interface;
* a configurable template/data-bank system;
* multiple real file-format generators;
* deterministic seeded generation;
* filesystem capacity management;
* run manifests;
* SHA-256 integrity verification;
* safe cleanup;
* extensible template packs;
* comprehensive tests;
* packaging for normal desktop users.

The codebase must be clean enough that additional file generators, template packs, data providers, profiles, and verification methods can be added later without restructuring the entire application.

The primary application name is:

**Chaff Generator**

The primary CLI command should be:

```text
chaff
```

The Python source package should use a collision-resistant internal name such as:

```text
chaff_generator
```

Do not choose or invent a software license unless explicitly instructed later.

---

# 2. Product Concept

"Chaff" means generated dummy data intended to simulate the kinds of files normally found on computers and storage devices.

Chaff Generator should create realistic but entirely synthetic files including things such as:

* text documents;
* notes;
* Markdown;
* logs;
* emails;
* office documents;
* spreadsheets;
* presentations;
* PDFs;
* CSV exports;
* JSON data;
* XML;
* HTML;
* contacts;
* calendar events;
* generated reports;
* invoices;
* receipts;
* meeting notes;
* project documents;
* lists;
* correspondence;
* administrative records;
* developer-oriented text files;
* optional large storage-test payloads.

The generated content must not simply contain repeated Lorem Ipsum.

It should resemble ordinary synthetic computer data assembled from:

* word banks;
* phrase banks;
* sentence banks;
* names;
* synthetic organizations;
* synthetic projects;
* dates;
* amounts;
* structured records;
* reusable document templates;
* contextual entities;
* seeded random generation.

A major design goal is that multiple generated files should appear to belong to the same fictional environment.

For example, if a run creates a fictional company named:

```text
Northstar Equipment Group
```

then that organization may appear consistently in:

* emails;
* invoices;
* meeting notes;
* spreadsheets;
* presentations;
* project reports;
* contact records.

Do not independently randomize every individual field without context.

Create a coherent synthetic **generation universe** for each run.

---

# 3. Primary Use Cases

Design Chaff around these primary use cases.

## 3.1 Realistic Dummy Dataset Generation

Generate directories containing realistic fake data for:

* application testing;
* file-indexing testing;
* search testing;
* backup testing;
* synchronization testing;
* migration testing;
* demonstration environments;
* filesystem testing;
* development environments.

---

## 3.2 Storage Integrity Testing

Generate a known corpus containing hashes for every file.

Workflow:

```text
Generate Chaff
        ↓
Write manifest + hashes
        ↓
Store/use/test the drive
        ↓
Run Chaff Verify
        ↓
Compare every current file against manifest
        ↓
Report intact / missing / changed / corrupt files
```

This should be a first-class feature.

Do not consider Chaff generation complete without the ability to verify generated data later.

---

## 3.3 Free-Space Fill

Allow a user to intentionally consume free filesystem space using generated files.

This can be useful for:

* storage testing;
* capacity testing;
* filesystem behavior testing;
* backup testing;
* filling previously unused filesystem space.

Call this feature:

**Free-Space Fill**

Do NOT label it:

* Secure Erase
* Secure Wipe
* Guaranteed Sanitization

Chaff works at the filesystem/file level and must not claim to provide hardware-level sanitization.

---

## 3.4 Synthetic Workstation Generation

Allow profiles that create realistic directory structures resembling a workstation.

Examples:

### Office workstation

```text
Documents/
    Reports/
    Finance/
    Meetings/
    Projects/
    Clients/
    Policies/
Email/
Spreadsheets/
Presentations/
Downloads/
Archive/
```

### Personal computer

```text
Documents/
    Personal/
    Bills/
    Letters/
    Records/
Notes/
Downloads/
Email/
Calendar/
Contacts/
```

### Developer workstation

```text
Projects/
Documents/
Notes/
Exports/
Logs/
Config/
Data/
Downloads/
```

### Mixed workstation

Combine realistic personal, business, communication, and technical files.

---

# 4. Critical Architectural Requirement

The GUI MUST NOT contain the actual generation logic.

Use this conceptual architecture:

```text
                 ┌────────────────────┐
                 │    PySide6 GUI     │
                 └─────────┬──────────┘
                           │
                 ┌─────────▼──────────┐
                 │       CLI          │
                 │       Typer        │
                 └─────────┬──────────┘
                           │
          Both call the same application services
                           │
                ┌──────────▼──────────┐
                │   Chaff Core API    │
                └──────────┬──────────┘
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
Generation Engine    Verification Engine   Cleanup Engine
       │
       ├── Planner
       ├── World/Entity Generator
       ├── Template Engine
       ├── Content Banks
       ├── Renderers
       ├── Storage Budget
       └── Manifest Writer
```

A future application should be able to do:

```python
from chaff_generator import ChaffEngine

engine = ChaffEngine(config)
result = engine.generate()
```

without importing PySide6.

---

# 5. Recommended Technology Stack

Use:

```text
Python >= 3.12

Desktop UI:
    PySide6

CLI:
    Typer

Template engine:
    Jinja2

Template metadata:
    PyYAML using safe_load only

Office files:
    python-docx
    openpyxl
    python-pptx

PDF:
    ReportLab

Email:
    Python standard library email package

Mailbox formats:
    Python standard library mailbox package

Trash / Recycle Bin:
    Send2Trash

Configuration directories:
    platformdirs

Testing:
    pytest
    pytest-qt

Linting / formatting:
    Ruff

Type checking:
    mypy

Desktop packaging:
    PyInstaller
```

Avoid heavy dependencies such as pandas when ordinary Python data structures are sufficient.

Use a normal:

```text
pyproject.toml
```

based project.

---

# 6. Proposed Repository Architecture

Create approximately this architecture:

```text
chaff-generator/
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── AGENTS.md
├── src/
│   └── chaff_generator/
│       ├── __init__.py
│       ├── __main__.py
│       ├── version.py
│       │
│       ├── core/
│       │   ├── engine.py
│       │   ├── planner.py
│       │   ├── models.py
│       │   ├── events.py
│       │   ├── size.py
│       │   ├── paths.py
│       │   ├── filesystem.py
│       │   ├── hashing.py
│       │   └── errors.py
│       │
│       ├── content/
│       │   ├── bank.py
│       │   ├── context.py
│       │   ├── world.py
│       │   ├── entities.py
│       │   ├── generators.py
│       │   └── template_engine.py
│       │
│       ├── templates/
│       │   ├── loader.py
│       │   ├── models.py
│       │   ├── pack.py
│       │   └── validator.py
│       │
│       ├── renderers/
│       │   ├── base.py
│       │   ├── registry.py
│       │   ├── text.py
│       │   ├── markdown.py
│       │   ├── html.py
│       │   ├── csv.py
│       │   ├── json.py
│       │   ├── xml.py
│       │   ├── email.py
│       │   ├── mailbox.py
│       │   ├── docx.py
│       │   ├── pdf.py
│       │   ├── xlsx.py
│       │   ├── pptx.py
│       │   ├── calendar.py
│       │   ├── contact.py
│       │   └── payload.py
│       │
│       ├── manifest/
│       │   ├── models.py
│       │   ├── writer.py
│       │   ├── reader.py
│       │   └── verifier.py
│       │
│       ├── cleanup/
│       │   ├── manager.py
│       │   ├── safety.py
│       │   └── trash.py
│       │
│       ├── profiles/
│       │   ├── models.py
│       │   ├── loader.py
│       │   └── builtin.py
│       │
│       ├── cli/
│       │   ├── app.py
│       │   ├── generate.py
│       │   ├── verify.py
│       │   ├── cleanup.py
│       │   ├── packs.py
│       │   └── inspect.py
│       │
│       ├── gui/
│       │   ├── app.py
│       │   ├── main_window.py
│       │   ├── controllers/
│       │   ├── workers/
│       │   ├── widgets/
│       │   ├── pages/
│       │   │   ├── generate.py
│       │   │   ├── verify.py
│       │   │   ├── runs.py
│       │   │   ├── templates.py
│       │   │   └── settings.py
│       │   └── resources/
│       │
│       └── data/
│           └── default-pack/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── renderers/
│   ├── safety/
│   └── ui/
│
├── docs/
│   ├── architecture.md
│   ├── chaff-bank.md
│   ├── templates.md
│   ├── integrity-testing.md
│   ├── filesystem-safety.md
│   └── development.md
│
└── scripts/
    ├── build.py
    └── benchmark.py
```

Exact organization can be adjusted where justified, but preserve clear separation of concerns.

---

# 7. Core Job Configuration

Every generation run must be represented by a serializable configuration object.

Conceptually:

```yaml
schema_version: 1

target:
  path: "/media/user/test-drive"
  mode: bytes
  amount: "25 GiB"
  reserve: "2 GiB"

profile: mixed_workstation

seed: 192839102

date_range:
  start: "2023-01-01"
  end: "2026-08-01"

directory_layout:
  mode: realistic

file_types:
  txt:
    enabled: true
    weight: 10
  md:
    enabled: true
    weight: 5
  eml:
    enabled: true
    weight: 15
  docx:
    enabled: true
    weight: 15
  pdf:
    enabled: true
    weight: 15
  csv:
    enabled: true
    weight: 10
  xlsx:
    enabled: true
    weight: 10
  pptx:
    enabled: true
    weight: 5
  json:
    enabled: true
    weight: 5
  html:
    enabled: true
    weight: 5

integrity:
  create_manifest: true
  algorithm: sha256

completion:
  action: keep
```

The same configuration must be loadable from:

* GUI;
* CLI;
* JSON/YAML preset.

---

# 8. Storage Target Modes

Support three major target modes.

## 8.1 Generate Exact Amount

Example:

```text
Generate: 20 GiB
```

Track actual file bytes written.

---

## 8.2 Percentage of Currently Free Space

Example:

```text
Use 75% of currently available space.
```

Calculate from initial filesystem state and continuously recheck available space.

---

## 8.3 Fill Until Reserve Remains

Example:

```text
Continue until only 5 GiB free remains.
```

This is the preferred free-space-fill implementation.

Do not simply calculate the amount once and blindly write that many bytes.

Other applications may also be writing to the filesystem.

Continuously check available capacity.

Stop safely when the reserve threshold is reached.

---

# 9. Storage Safety

This section is mandatory.

Chaff intentionally creates large amounts of filesystem data, so safeguards must be stronger than a normal document generator.

## 9.1 Never Scatter Files Directly Into the Selected Directory

If the user chooses:

```text
/media/rob/testdrive
```

create:

```text
/media/rob/testdrive/Chaff_Run_20260816_183405_a84f/
```

All generated content belongs inside that run root.

---

## 9.2 Run Ownership Marker

Create an internal marker similar to:

```text
.chaff-run.json
```

containing:

* run UUID;
* application version;
* generation seed;
* creation timestamp;
* root path;
* manifest identity.

Cleanup MUST refuse destructive operations if this marker is absent or invalid.

---

## 9.3 Path Containment

Every generated and deleted path must resolve underneath the run root.

Implement reusable path checks.

Protect against:

```text
../
absolute paths
symlinks
junctions
template-generated path traversal
```

Never follow a generated symlink outside the run.

Prefer not to generate symlinks at all.

---

## 9.4 Never Delete Arbitrary Target Contents

This is unacceptable:

```python
shutil.rmtree(user_selected_directory)
```

Instead, cleanup must only act on a validated Chaff run root.

Existing user files beside the Chaff run must remain untouched.

---

## 9.5 Never Perform Raw Block-Device Operations

The application must not:

* format disks;
* write directly to `/dev/sdX`;
* manipulate partitions;
* invoke raw disk APIs;
* issue firmware erase commands.

Chaff is a filesystem-level application.

---

## 9.6 No Privilege Escalation

Do not automatically invoke:

```text
sudo
pkexec
runas
```

or equivalent elevation.

If the target is not writable, explain the error.

---

## 9.7 Disk Reserve

Default to a conservative free-space reserve.

Make the reserve user configurable.

Allow advanced users to override it, but clearly warn when they attempt to leave essentially no free space.

---

# 10. Size Units

Support both decimal and binary units:

```text
KB
MB
GB
TB

KiB
MiB
GiB
TiB
```

Convert everything internally to integer bytes.

Never use floating-point byte counters internally.

Implement:

```python
parse_size("1.5 GiB")
format_size(1610612736)
```

with comprehensive unit tests.

---

# 11. Generation Seed and Reproducibility

Every run gets a master seed.

The user may:

* enter one;
* generate a random one;
* copy it;
* reuse it later.

Store it in the manifest.

Do not rely on the process-wide `random` module state.

Create isolated RNG instances.

For individual files, derive a deterministic file seed using the master seed and file index.

Conceptually:

```text
master seed
    +
file index
    ↓
SHA-256
    ↓
file-specific seed
```

This means parallel execution or retry order does not change which random values belong to each planned file.

Define reproducibility carefully:

* filenames and generated semantic data should be deterministic for the same application/template versions and seed;
* the original run manifest remains the authoritative source for byte-level integrity verification;
* do not promise that Office/PDF files regenerated years later under different dependency versions will be byte-for-byte identical.

Record dependency/application versions in manifests where reasonable.

---

# 12. ChaffBank

Create a formal content/template system called:

**ChaffBank**

The default data bundle should live independently of application code.

Example:

```text
default-pack/
├── pack.yaml
├── words/
│   ├── nouns.txt
│   ├── verbs.txt
│   ├── adjectives.txt
│   ├── adverbs.txt
│   ├── technologies.txt
│   ├── products.txt
│   └── topics.txt
├── phrases/
│   ├── greetings.txt
│   ├── closings.txt
│   ├── project_status.txt
│   └── meeting_actions.txt
├── sentences/
│   ├── business.txt
│   ├── personal.txt
│   ├── technical.txt
│   ├── finance.txt
│   ├── project_updates.txt
│   └── support.txt
├── entities/
│   ├── first_names.txt
│   ├── last_names.txt
│   ├── departments.txt
│   ├── company_words.txt
│   ├── job_titles.txt
│   ├── cities.json
│   └── products.json
├── templates/
│   ├── prose/
│   ├── email/
│   ├── spreadsheet/
│   ├── presentation/
│   ├── records/
│   └── developer/
└── profiles/
    ├── office.yaml
    ├── personal.yaml
    ├── developer.yaml
    └── mixed.yaml
```

---

# 13. ChaffBank Pack Metadata

Every pack must contain metadata.

Example:

```yaml
id: builtin.en.general
name: Chaff General English
version: 1.0.0
language: en
description: Built-in general-purpose synthetic data pack.
author: Chaff Generator
minimum_chaff_version: 0.1.0
```

Eventually third parties should be able to create their own packs.

Design for that now.

Do not require an online repository or marketplace in v1.

---

# 14. Word and Sentence Bank Format

Basic text banks should remain easy to edit.

Example:

```text
# sentences/business-status.txt

The project remains on schedule for the current reporting period.
The team completed the scheduled review this week.
Several outstanding items require follow-up before the next milestone.
```

Ignore:

* blank lines;
* comment lines beginning with `#`.

Sentence-bank entries may themselves contain template variables:

```text
The {{ project.name }} team completed {{ integer(2, 12) }} outstanding tasks this week.
```

Allow controlled recursive rendering of bank entries.

Protect against:

* recursive loops;
* excessive nesting;
* self-reference.

Set a small maximum recursive expansion depth such as 5.

---

# 15. Template Language

Use Jinja as the underlying engine.

Expose a constrained Chaff-specific template vocabulary.

Use syntax such as:

```jinja
{{ person.full_name }}
{{ person.first_name }}
{{ company.name }}
{{ project.name }}
{{ project.code }}

{{ word("technology") }}
{{ pick("phrases.greetings") }}
{{ sentence("business") }}
{{ paragraph("business", 4) }}

{{ integer(1, 100) }}
{{ decimal(10, 5000, 2) }}
{{ money(50, 5000) }}

{{ date_recent() }}
{{ date_between("2024-01-01", "2026-01-01") }}

{{ uuid() }}

{{ email_address(person) }}
{{ phone_number() }}
```

Provide useful filters:

```jinja
{{ project.name | slug }}
{{ person.full_name | upper }}
{{ amount | currency }}
{{ event.date | datefmt("%B %d, %Y") }}
```

---

# 16. Template Security

Use a sandboxed Jinja environment.

Use:

```text
StrictUndefined
```

so missing variables fail visibly instead of silently generating malformed documents.

Do NOT expose:

* Python builtins;
* arbitrary attribute traversal;
* filesystem functions;
* environment variables;
* imports;
* subprocess;
* networking;
* `eval`;
* `exec`.

Template packs are data, not executable Python plugins.

Use safe YAML parsing only.

---

# 17. Synthetic Data Safety

Default generated identities should be obviously synthetic internally while still looking plausible.

For email addresses prefer reserved/non-routable examples such as:

```text
alex.morgan@example.com
billing@northstar.example
```

Do not ship scraped customer databases or real personal datasets.

The built-in ChaffBank should consist of:

* project-authored content;
* appropriately licensed data;
* public-domain data where intentionally used.

Record pack attribution/license metadata when external data sources are ever introduced.

---

# 18. Generation Universe

Before generating individual files, build a coherent `GenerationWorld`.

Example model:

```text
GenerationWorld
├── primary_user
├── household
├── organization
├── employees
├── contacts
├── clients
├── vendors
├── projects
├── products
├── transactions
├── meetings
├── date_range
└── recurring topics
```

The world should contain persistent entities reused across documents.

For example:

```python
world.projects[0]
```

could produce:

```text
Project:
    name: Northwind Migration
    code: NM-204
    manager: Morgan Chen
    start_date: 2025-03-12
    budget: 184250
```

Generated files may then naturally include:

```text
NM-204 Project Update.docx
NM-204 Budget.xlsx
Northwind Migration Kickoff.pptx
Meeting Notes - NM-204.md
Re: Northwind Migration.eml
```

This coherence is extremely important.

---

# 19. Internal Semantic Document Models

Do not make every output renderer independently invent its content.

Introduce a small number of semantic intermediate models.

At minimum:

```text
ProseDocument
EmailDocument
TabularDocument
PresentationDocument
RecordCollection
CalendarDocument
ContactDocument
```

Example:

```python
class ProseDocument:
    title
    author
    created_at
    sections
    metadata
```

A section can contain:

```text
Heading
Paragraph
BulletList
NumberedList
Table
Quote
PageBreak
```

Then:

```text
ProseDocument
    ├── TXT renderer
    ├── Markdown renderer
    ├── HTML renderer
    ├── DOCX renderer
    └── PDF renderer
```

This prevents five independent copies of every report template.

---

# 20. Renderer Architecture

Every file renderer must implement a shared protocol.

Conceptually:

```python
class Renderer(Protocol):
    id: str
    extension: str

    def render(
        self,
        document,
        destination: Path,
        context: RenderContext,
    ) -> RenderResult: ...
```

A renderer should declare capabilities such as:

```text
supports_exact_size
supports_target_size
supports_streaming
semantic_document_type
default_size_range
```

Use a renderer registry.

Do not create a giant:

```python
if extension == ...
elif extension == ...
elif extension == ...
```

throughout the application.

---

# 21. Initial Supported File Formats

Implement these as genuine valid files.

## Plain text

```text
.txt
.log
```

---

## Lightweight structured text

```text
.md
.html
.csv
.json
.xml
```

---

## Email

```text
.eml
```

Use proper email headers and MIME structures.

Support:

* From
* To
* Cc
* Subject
* Date
* Message-ID
* text/plain
* text/html multipart email
* synthetic attachments

Optional mailbox-level output:

```text
mbox
Maildir
```

---

## Word processing

```text
.docx
```

Use python-docx.

Generate genuine:

* headings;
* paragraphs;
* lists;
* tables;
* headers/footers where appropriate;
* document metadata.

Do not create text files renamed to `.docx`.

Do not attempt legacy binary `.doc` in the initial version.

---

## PDF

```text
.pdf
```

Use ReportLab or another direct Python PDF generator.

Create real documents with:

* headings;
* paragraphs;
* tables;
* page numbers;
* realistic margins;
* multiple pages where appropriate.

---

## Spreadsheet

```text
.xlsx
```

Use openpyxl.

Generate realistic sheets such as:

* expenses;
* inventory;
* budgets;
* invoices;
* project tracking;
* sales;
* timesheets;
* contact exports.

Use:

* data types;
* dates;
* currency;
* formulas where appropriate;
* column widths;
* headers;
* multiple sheets occasionally.

---

## Presentations

```text
.pptx
```

Use python-pptx.

Generate:

* title slide;
* section slides;
* bullet slides;
* project summaries;
* simple tables/charts where feasible;
* closing slide.

---

## Contacts

Support:

```text
.vcf
```

---

## Calendar

Support:

```text
.ics
```

---

# 22. Optional Storage-Test Payload

Include an explicitly optional renderer:

```text
.dat
or
.bin
```

This is not part of the "realistic documents" category.

Its purpose is rapid storage consumption and integrity testing.

Call it:

**Storage Payload**

Generate actual bytes.

Do not create sparse files using only:

```python
truncate()
```

For deterministic payloads, derive byte chunks from:

```text
run seed
+
file identifier
+
chunk index
```

using a deterministic hash-based stream.

Write data incrementally.

Never hold a multi-gigabyte payload in memory.

The storage payload option should default to OFF for realistic workstation profiles and may default ON for dedicated storage-test profiles.

---

# 23. File Size Profiles

Different file formats require different realistic sizes.

Implement configurable distributions.

Example categories:

```text
tiny
small
medium
large
very_large
```

Example conceptual ranges:

```text
TXT:
    1 KiB – 20 MiB

EML:
    2 KiB – 5 MiB

DOCX:
    10 KiB – 3 MiB

PDF:
    10 KiB – 15 MiB

CSV:
    5 KiB – 100 MiB

JSON:
    5 KiB – 100 MiB

XLSX:
    10 KiB – 30 MiB

PPTX:
    50 KiB – 10 MiB

Storage Payload:
    1 MiB – multiple GiB
```

These should be profile configuration rather than hardcoded throughout renderer code.

---

# 24. Generation Planner

Create the complete generation plan before writing wherever practical.

The planner determines:

* target bytes;
* directory structure;
* approximate file count;
* file-format distribution;
* template selection;
* intended file sizes;
* file seeds;
* destination paths.

Represent planned files as objects.

Example:

```python
PlannedFile(
    index=193,
    relative_path="Documents/Projects/NM-204/Status Report.docx",
    renderer="docx",
    template_id="prose.project_status",
    desired_size=184_000,
    seed=...,
)
```

---

# 25. Avoid Millions of Tiny Files by Accident

A 500 GiB job consisting primarily of 20 KiB Word documents would create an absurd number of files.

Before generation, estimate:

```text
expected file count
```

Display the estimate.

Profiles should control file density.

Provide presets such as:

## Realistic Desktop

Many small-to-medium realistic files.

## Balanced

Realistic files plus larger CSV, logs, attachments, and PDFs.

## Storage Test

A representative set of normal files plus large deterministic storage payloads.

## Custom

User controls everything.

Warn if the estimated file count is extremely high.

---

# 26. Exact Target Handling

Container formats such as DOCX/XLSX/PPTX may not end up exactly at their requested size.

Therefore the overall generation engine should target total run size rather than assuming every individual renderer hits an exact number.

Algorithm:

```text
Generate planned files
        ↓
Check actual bytes written
        ↓
Calculate remaining target
        ↓
Continue generating appropriate files
        ↓
Use an exact-size-capable finalizer where permitted
        ↓
Finish as close to target as possible
```

TXT, LOG, or Storage Payload renderers can be used as exact-size finalizers.

Never intentionally exceed the configured filesystem safety reserve merely to hit an exact logical-byte target.

Safety wins over precision.

---

# 27. Streaming

Large generation jobs must have bounded memory use.

Do not build:

```python
huge_string = "..." * 10_000_000
```

Use chunked output for:

* TXT;
* LOG;
* CSV;
* JSON where feasible;
* XML where feasible;
* storage payloads;
* hashing.

Use reasonable chunks such as approximately 1–8 MiB.

Office documents should remain reasonably sized so their libraries do not require enormous memory.

---

# 28. Partial Files and Atomic Completion

Write files initially with an internal temporary name such as:

```text
filename.docx.chaff-partial
```

After successful rendering:

1. flush/close the file;
2. determine final size;
3. hash it;
4. atomically rename/replace it to its final name;
5. append it to the manifest journal.

On interruption, incomplete temporary files can therefore be identified safely.

---

# 29. Filename Generation

Create realistic filenames.

Examples:

```text
Quarterly Operations Review - Q2 2026.docx
Project NM-204 Status Report.pdf
Meeting Notes - August 14.md
2026 Expense Summary.xlsx
Invoice 10482.pdf
Reimbursement Request.eml
Customer Export 2026-07.csv
Deployment Notes.txt
```

Implement:

* filename sanitization;
* Windows reserved-name avoidance;
* illegal-character removal;
* configurable filename length;
* path-length awareness;
* collision resolution.

For collisions use meaningful deterministic suffixes rather than overwriting existing files.

Never overwrite pre-existing user files.

---

# 30. Realistic Folder Hierarchies

Support:

```text
flat
simple
realistic
custom
```

The realistic profile should generate paths based on the synthetic world.

Example:

```text
Documents/
├── Finance/
│   ├── Expenses/
│   ├── Invoices/
│   └── Budgets/
├── Projects/
│   ├── Northwind Migration/
│   └── Customer Portal/
├── Meetings/
├── Reports/
├── Personal/
└── Archive/

Email/
├── Inbox/
├── Sent/
└── Archive/

Spreadsheets/
Presentations/
Notes/
Downloads/
Data/
```

Do not make every run use precisely the same tree.

Variation should be seed driven.

---

# 31. Generated Email

Email generation should be particularly rich.

Generate several categories:

* ordinary correspondence;
* project updates;
* meeting scheduling;
* support messages;
* purchase confirmations;
* internal announcements;
* follow-ups;
* reminders;
* invoices;
* newsletters;
* system-style notifications.

Some messages should form threads.

Thread fields should reuse:

```text
Subject
Message-ID
In-Reply-To
References
Participants
```

Generate plausible date ordering.

Some messages may have generated attachments.

No email must ever be transmitted.

Chaff does not need SMTP functionality.

---

# 32. Templates

Examples of prose templates to ship:

```text
business_memo
project_status
meeting_minutes
technical_report
incident_summary
expense_report
letter
policy_note
research_notes
proposal
invoice
receipt
personal_letter
todo_list
journal_note
README
installation_notes
```

Email templates:

```text
project_update
meeting_invitation
meeting_followup
invoice_email
support_request
support_reply
internal_notice
newsletter
personal_message
order_confirmation
```

Spreadsheet templates:

```text
budget
expenses
inventory
timesheet
project_tracker
customer_export
sales_report
asset_register
invoice_lines
```

Presentation templates:

```text
project_update
quarterly_review
proposal
training_deck
meeting_brief
```

---

# 33. Template Example

A template might conceptually resemble:

```yaml
id: prose.project_status
kind: prose

title: "{{ project.name }} Status Report"

author: "{{ primary_user.full_name }}"

sections:
  - heading: Executive Summary
    paragraphs:
      - "{{ paragraph('project_status', 4) }}"

  - heading: Current Activities
    bullets:
      - "{{ sentence('project_activity') }}"
      - "{{ sentence('project_activity') }}"
      - "{{ sentence('project_activity') }}"

  - heading: Budget
    table:
      columns:
        - Category
        - Budget
        - Actual
      rows:
        - ["Labour", "{{ money(5000, 50000) }}", "{{ money(5000, 50000) }}"]
        - ["Materials", "{{ money(1000, 20000) }}", "{{ money(1000, 20000) }}"]

  - heading: Next Steps
    paragraphs:
      - "{{ paragraph('next_steps', 3) }}"
```

The same semantic document can then be emitted as:

```text
DOCX
PDF
HTML
Markdown
TXT
```

---

# 34. Manifest System

Every run should optionally create:

```text
chaff-manifest.json
```

and preferably a journal during generation:

```text
chaff-manifest.journal
```

The journal protects progress if the application crashes before the final manifest is assembled.

Manifest metadata should include:

```text
schema version
run UUID
application version
creation time
completion time
seed
selected profile
source ChaffBank pack/version
target mode
requested bytes
actual generated bytes
initial filesystem free space
final filesystem free space
file count
status
dependency information where useful
```

For each file:

```text
relative path
renderer/file type
size
SHA-256
template ID
file seed
creation order
```

Do not store absolute paths for each individual file if a relative path is sufficient.

---

# 35. Integrity Verification

Implement a separate verification engine.

Modes:

## Metadata Verification

Check:

* file exists;
* expected path;
* expected size.

Fast but does not detect every corruption type.

---

## Full Verification

Read every generated file and calculate SHA-256.

Compare with manifest.

Classify each result:

```text
INTACT
MISSING
SIZE_MISMATCH
HASH_MISMATCH
UNREADABLE
```

---

## Sample Verification

User selects:

```text
percentage
or
number of files
```

Select the sample deterministically when given a verification seed.

Useful for very large drives.

---

# 36. Verification Report

Display:

```text
Files expected:       18,451
Files verified:       18,451
Files intact:         18,449
Files missing:             1
Files changed:             1
Unreadable:                0
Bytes verified:       248.7 GiB
```

Allow export to:

```text
JSON
CSV
```

List precise affected files.

---

# 37. Future Corruption Simulation

Architect the verifier so a future development phase can introduce an advanced:

**Corruption Lab**

that deliberately:

* changes random bytes;
* truncates selected generated files;
* removes generated files;

strictly inside a validated Chaff run.

This would permit verifier testing.

Do not make it necessary for the initial MVP.

---

# 38. Cleanup Modes

After a completed run, support:

```text
Keep
Delete
Move to Trash / Recycle Bin
```

Potential additional workflow:

```text
Verify then Delete
```

Keep must be the safest/default option.

---

# 39. Delete Operation

Deletion must:

1. read the Chaff run marker;
2. validate run UUID;
3. validate path containment;
4. confirm the root belongs to Chaff;
5. remove only owned content.

Never implement an arbitrary-directory delete button.

---

# 40. Trash Operation

For Trash/Recycle Bin behavior:

Prefer moving the complete validated Chaff run root to Trash rather than calling the trash operation once for every generated file.

Explain in the UI that placing a large run in Trash may not immediately reclaim storage until the operating system's Trash/Recycle Bin is emptied.

---

# 41. Automatic Completion Action

Allow the user to configure:

```text
When generation completes:
    Keep files
    Delete generated run
    Move generated run to Trash
```

For destructive automatic actions, require explicit selection.

Never make automatic deletion the default.

If generation fails or is cancelled, do not automatically destroy evidence/debugging information unless an explicit setting requires partial cleanup.

---

# 42. GUI

Build a polished desktop utility using PySide6.

Do not create a crude developer-only form.

Primary navigation:

```text
Generate
Verify
Runs
ChaffBank
Settings
```

---

# 43. Generate Page

Organize the Generate interface into clear groups.

## Destination

Show:

```text
Target directory
Filesystem
Available space
Requested amount
Estimated remaining space
```

Include a native directory picker.

---

## Amount

Controls:

```text
Mode:
    Generate amount
    Percentage of free space
    Fill until reserve

Value:
    [ numeric field ] [ unit ]

Reserve:
    [ numeric field ] [ unit ]
```

---

## Generation Profile

Choices:

```text
Realistic Desktop
Office Workstation
Personal Computer
Developer Workstation
Balanced
Storage Test
Custom
```

---

## File Types

Provide checkbox/toggle controls for:

```text
Text
Markdown
Logs
HTML
CSV
JSON
XML
Email
Word Documents
PDF
Spreadsheets
Presentations
Contacts
Calendar
Storage Payload
```

When Custom is selected, expose relative weights.

---

## Directory Layout

```text
Realistic hierarchy
Simple hierarchy
Flat
```

---

## Reproducibility

Show:

```text
Seed
[__________________]

Generate random seed
Copy seed
```

---

## Completion Action

```text
Keep
Delete
Move to Trash
```

---

## Integrity

```text
Create SHA-256 manifest
```

Default enabled.

---

# 44. Preflight Summary

Before starting, calculate and show:

```text
Destination
Initial free space
Requested generation
Expected remaining free space
Estimated number of files
Selected formats
Profile
Seed
Completion action
Manifest enabled
```

If the operation may leave dangerously little filesystem space, display a clear warning.

---

# 45. Active Generation View

When generation begins, replace or transition the form to an operational progress view.

Show:

```text
Overall progress
Data written
Target data
File count
Current file
Current file type
Generation throughput
Elapsed time
Estimated remaining time
Free filesystem space
Errors/warnings
```

Controls:

```text
Pause
Resume
Cancel
```

The GUI must remain responsive.

Do not execute generation on the Qt UI thread.

---

# 46. Progress Events

The core engine should publish events independent of Qt.

For example:

```text
RunStarted
FileStarted
FileCompleted
ProgressUpdated
WarningRaised
FileFailed
RunPaused
RunResumed
RunCancelled
RunCompleted
```

The GUI adapts these to Qt signals.

The CLI adapts them to terminal output.

Rate-limit progress events so thousands of tiny files do not overwhelm the interface.

---

# 47. Cancellation

Cancellation should be cooperative and safe.

The engine should check cancellation:

* between files;
* during long streaming writes;
* during verification.

A cancelled run should become:

```text
status = cancelled
```

rather than pretending it completed.

The partial manifest/journal must remain usable.

---

# 48. Verify Page

Allow:

```text
Select Chaff run directory
or
Select chaff-manifest.json
```

Automatically inspect metadata.

Display:

```text
Run date
Seed
Generated size
File count
Profile
Original Chaff version
```

Verification choices:

```text
Metadata
Sample
Full
```

Then present the verification report.

---

# 49. Runs Page

Maintain lightweight local history of recently generated or verified runs.

Do not require a central database server.

Use application-local JSON or SQLite only if it materially improves the implementation.

Run history may record:

```text
run UUID
path
date
size
file count
profile
status
last verification
```

The authoritative run information remains its manifest.

---

# 50. ChaffBank UI

Provide an initial ChaffBank management interface.

Display installed packs:

```text
Name
ID
Version
Language
Status
Location
```

Actions:

```text
Validate
Preview
Enable
Disable
Import Pack
Open Folder
```

Do not implement an internet marketplace.

---

# 51. Template Preview

Allow a developer/user to choose a template and preview generated structured content using a selected seed.

This will be extremely valuable when building new ChaffBanks.

Display template errors clearly.

For example:

```text
Unknown variable:
    project.owner_nme

Did you mean:
    project.owner_name
```

where practical.

---

# 52. Template Pack Import Security

If packs may be imported from ZIP files:

Prevent Zip Slip.

Reject archive entries with:

```text
../
absolute paths
drive-letter paths
symlinks
```

Set reasonable extraction size and file-count limits.

Template packs must not install Python modules.

They contain data/templates only.

---

# 53. CLI

The GUI is primary, but provide a complete headless interface.

Expected commands:

```text
chaff
chaff generate
chaff verify
chaff clean
chaff inspect
chaff packs
```

Running:

```text
chaff
```

without a subcommand should open the GUI where appropriate.

Examples:

```bash
chaff generate \
  --target /mnt/test \
  --size "20 GiB" \
  --profile mixed \
  --types txt,eml,docx,pdf,xlsx \
  --seed 481925
```

Example free-space fill:

```bash
chaff generate \
  --target /mnt/test \
  --fill-free-space \
  --reserve "5 GiB" \
  --profile storage-test
```

Verification:

```bash
chaff verify /mnt/test/Chaff_Run_.../chaff-manifest.json
```

Cleanup:

```bash
chaff clean /mnt/test/Chaff_Run_... \
  --mode delete
```

Pack validation:

```bash
chaff packs validate ./my-chaff-pack
```

---

# 54. Preset Files

Allow generation configuration to be exported:

```text
my-drive-test.chaff.yaml
```

and reused:

```bash
chaff generate --config my-drive-test.chaff.yaml
```

Presets should not silently override safety validation.

---

# 55. Error Handling

Create domain-specific exceptions.

Examples:

```text
ChaffError
ConfigurationError
InsufficientSpaceError
UnsafePathError
TemplateError
RendererError
ManifestError
VerificationError
CleanupSafetyError
```

GUI errors should become useful messages.

CLI errors should produce:

* concise explanation;
* nonzero exit code;
* optional verbose traceback.

Do not expose giant Python tracebacks to ordinary GUI users unless a diagnostics/details view is opened.

---

# 56. Logging

Use Python logging.

Keep:

```text
INFO
WARNING
ERROR
DEBUG
```

levels.

Log useful data such as:

* run IDs;
* major state transitions;
* renderer failures;
* cleanup events;
* verification failures.

Do not log every generated sentence or giant content body.

Provide an optional verbose/debug mode.

---

# 57. Filesystem Error Recovery

Handle:

```text
permission denied
disk full
filesystem disappears
read-only filesystem
filename/path invalid
file temporarily locked
I/O error
renderer exception
```

A single failed document should not automatically corrupt the entire run state.

Depending on severity:

* mark the file failed and continue;
* pause the run;
* terminate safely.

Disk-full behavior must terminate writing gracefully and preserve the manifest journal.

---

# 58. Free-Space Monitoring

Do not rely only on the original free-space measurement.

Periodically check:

```python
shutil.disk_usage(target)
```

or equivalent abstractions.

Stop before violating configured reserve.

The generation progress model should track both:

```text
logical generated bytes
current filesystem free bytes
```

This is important because filesystem allocation, compression, metadata, and other processes can cause free-space changes that do not exactly match the sum of file sizes.

---

# 59. Do Not Create Sparse Storage-Test Files

The storage-test mode must physically write file data through the filesystem.

Do not use:

```python
seek()
truncate()
fallocate()
```

as a substitute for generating data when the purpose is storage consumption.

A sparse 100 GiB file that occupies almost no blocks is not equivalent to writing 100 GiB of Chaff.

---

# 60. Hashing

Use SHA-256 through Python `hashlib`.

Hash using streaming reads/chunks.

Do not load complete multi-gigabyte files into RAM to hash them.

The manifest hashes represent actual generated bytes.

---

# 61. Performance Architecture

Do not optimize prematurely at the expense of correctness.

Start with a reliable single-worker implementation.

Architect the planner so safe parallel generation can be introduced later.

If concurrency is added:

* planning remains deterministic;
* each file has an independent seed;
* manifest writing is synchronized;
* GUI event updates remain ordered enough to understand;
* disk thrashing is avoided.

Provide a configurable worker count only after correctness is proven.

---

# 62. Generated Content Quality

Avoid obviously mechanical output such as:

```text
Word word word word word.
Lorem ipsum...
Random 39283 text 92839.
```

Use varied sentence structures and consistent contexts.

The default ChaffBank should contain enough original fragments to prevent extremely obvious repetition.

Include vocabulary for:

```text
business
administration
finance
project management
technology
operations
personal correspondence
meetings
customer service
general notes
planning
purchasing
inventory
```

---

# 63. Repetition Control

Track recently selected:

```text
sentences
templates
names
subjects
```

within reasonable windows.

Avoid selecting the same sentence repeatedly in a single short document.

Do not globally ban repetition because natural data contains repetition.

Use weighted variation instead.

---

# 64. Dates and Timeline Consistency

Use the configured run date range.

If:

```text
Project starts March 2025
```

do not create its project completion report dated January 2024.

Email threads must proceed chronologically.

Invoice due dates must follow invoice dates.

Meeting follow-ups should follow meeting dates.

Build small consistency helpers instead of independently randomizing every date.

---

# 65. Metadata

Where file formats support it, populate synthetic metadata such as:

```text
title
author
subject
created date
modified date
company
keywords
```

Use the generation universe.

Do not leak the actual host user's personal details into Chaff documents unless explicitly requested.

---

# 66. Attachments

Emails may attach previously or independently generated Chaff files.

Possible attachments:

```text
PDF invoice
DOCX report
XLSX expense sheet
TXT notes
CSV export
```

References must stay inside the generated corpus.

Do not attach files from the user's actual computer.

---

# 67. Advanced Developer Profile

The Developer Workstation profile may additionally create harmless text-based files such as:

```text
.py
.js
.ts
.tsx
.css
.sql
.yaml
.yml
.toml
.ini
.env.example
Dockerfile
README.md
```

Content should be syntactically plausible and benign.

Never generate active malware, credential-stealing code, destructive scripts, or real secrets.

Generated configuration credentials must be clearly synthetic.

---

# 68. Generated Archives — Later Phase

Architect for future support for:

```text
.zip
.tar
.tar.gz
```

containing generated Chaff.

Do not make archive generation part of the first required MVP if it complicates target-byte accounting.

---

# 69. Profiles

Represent profiles as data.

Example:

```yaml
id: office-workstation
name: Office Workstation

directory_layout: office

format_weights:
  eml: 20
  docx: 18
  pdf: 15
  xlsx: 12
  txt: 10
  md: 5
  csv: 8
  pptx: 7
  json: 3
  html: 2

content_domains:
  business: 40
  projects: 25
  finance: 15
  meetings: 10
  technical: 10
```

Do not bury profiles as dozens of hardcoded `if` statements.

---

# 70. Manifest Durability

During large jobs, do not wait until the final byte to record every file.

Maintain a safe incremental journal.

After each completed file or controlled batch:

```text
append record
flush periodically
```

When a run completes:

1. consolidate journal;
2. create final manifest;
3. mark run complete.

When Chaff finds an interrupted run, it should be able to inspect its journal.

---

# 71. Resume — Architecture Now, Full Implementation Later

Design data structures so interrupted runs can eventually be resumed.

MVP does not need perfect automatic resume if it significantly increases complexity.

However, do not make resume impossible through architecture.

Each planned file has an identity and completed files are recorded.

---

# 72. Development Safety

This instruction is mandatory for the coding agent.

NEVER test Chaff by filling the development machine's real filesystem.

Automated tests must use:

```python
tempfile.TemporaryDirectory()
```

or pytest's:

```text
tmp_path
```

Do not run multi-gigabyte generation during implementation.

Ordinary integration tests should stay in approximately:

```text
1–50 MiB
```

ranges.

If a larger manual benchmark is needed, create a benchmark script but DO NOT automatically execute it.

Mock free-space calculations when testing fill-until-reserve behavior.

Never test destructive cleanup against:

```text
/
C:\
$HOME
Documents
Downloads
repository root
```

All destructive tests must occur inside a disposable temporary directory created by the test itself.

---

# 73. Unit Tests

Create tests for at least:

## Size parsing

```text
10 MB
1.5 GiB
500 KiB
2 TB
invalid values
negative values
overflow/bounds
```

## Path safety

Test:

```text
normal child
../ traversal
absolute path
symlink escape
run marker mismatch
wrong run UUID
```

## Deterministic content

Same:

```text
seed + template + world
```

must produce the same semantic content.

Different seed should generally change it.

## Template system

Test:

```text
word()
sentence()
paragraph()
pick()
integer()
money()
dates
StrictUndefined
recursive expansion
recursion limits
```

## Manifest

Test:

```text
write
read
journal
finalize
invalid manifest
schema version
```

## Cleanup

Ensure unrelated files always survive.

---

# 74. Renderer Tests

Every renderer must have tests proving it creates an actual valid file.

Examples:

DOCX:

```python
Document(generated_path)
```

must be able to open it.

XLSX:

```python
load_workbook(generated_path)
```

must succeed.

PPTX:

```python
Presentation(generated_path)
```

must succeed.

Email:

parse generated bytes with Python's email parser.

JSON:

```python
json.load()
```

must succeed.

XML:

parse it.

PDF:

validate signature/basic parser where practical.

Do not merely assert that a file exists.

---

# 75. Critical End-to-End Integrity Test

Create this integration test:

```text
1. Generate ~20 MiB mixed Chaff into tmp_path.

2. Verify manifest.
   Expected:
       all intact.

3. Modify one generated file.

4. Delete a second generated file.

5. Verify again.
   Expected:
       one HASH_MISMATCH
       one MISSING

6. Place an unrelated user.txt beside the Chaff run.

7. Run Chaff cleanup.

8. Assert:
       Chaff run removed
       user.txt remains completely untouched.
```

This is one of the project's most important tests.

---

# 76. UI Tests

Use pytest-qt for important interaction tests.

At minimum test:

* application launches;
* target selector model updates;
* invalid target blocks Start;
* amount validation;
* profile selection;
* start button state;
* cancellation event;
* verification results render.

Do not attempt to exhaustively pixel-test the interface.

---

# 77. Static Quality

Configure:

```text
ruff
mypy
pytest
```

Avoid unnecessary:

```text
Any
# type: ignore
```

Keep public core interfaces typed.

Use dataclasses or validated models consistently rather than loose unstructured dictionaries throughout the codebase.

---

# 78. Documentation

Create useful project documentation.

## README.md

Include:

```text
What Chaff is
Primary use cases
Screenshots placeholder only if no screenshots exist yet
Installation
Running GUI
Running CLI
Basic generation example
Integrity verification
Template packs
Important storage/sanitization disclaimer
Development
```

## docs/architecture.md

Explain the major components and data flow.

## docs/chaff-bank.md

Explain:

* word banks;
* sentence banks;
* packs;
* entity data;
* templates.

## docs/templates.md

Document all supported Jinja helpers.

## docs/integrity-testing.md

Explain:

```text
generate → manifest → verify
```

## docs/filesystem-safety.md

Document Chaff's containment and cleanup protections.

---

# 79. Sanitization Disclaimer

Documentation and UI must clearly distinguish:

```text
filesystem free-space filling
```

from:

```text
guaranteed media sanitization
```

Suggested language:

> Chaff Generator creates and deletes ordinary filesystem files. Free-Space Fill may be useful for storage testing and overwriting currently addressable free filesystem space, but it is not a substitute for device-appropriate sanitization, cryptographic erase, secure erase, or physical destruction where those methods are required.

Do not make security claims that cannot be proven.

---

# 80. Application Startup Behavior

Support:

```bash
python -m chaff_generator
```

and:

```bash
chaff
```

for the normal UI.

CLI subcommands must bypass GUI initialization.

A headless Linux environment running:

```bash
chaff verify ...
```

must not need to initialize Qt.

---

# 81. Packaging

Prepare PyInstaller configuration for:

```text
Windows
Linux
macOS
```

Build separately for each target OS.

Ensure bundled applications include:

* built-in ChaffBank;
* templates;
* icons/resources;
* renderer dependencies.

Do not assume a user has:

* Python;
* Microsoft Office;
* LibreOffice.

The initial generators should directly create their supported formats.

---

# 82. CI

Create a sensible CI workflow that runs:

```text
ruff
mypy
pytest
```

on supported Python environments.

Where practical use:

```text
Linux
Windows
macOS
```

because filesystem behavior is important to this project.

Do not run free-space-fill benchmarks in CI.

---

# 83. Development Phases

Implement in the following order.

## Phase 1 — Foundation

Build:

* project structure;
* config models;
* size parsing;
* safe paths;
* event system;
* content RNG;
* ChaffBank loader;
* Jinja sandbox;
* base renderer system.

Tests must pass.

---

## Phase 2 — Core Text Generation

Implement:

```text
TXT
LOG
Markdown
HTML
CSV
JSON
XML
```

Implement:

* directory planner;
* generation world;
* template selection;
* run marker;
* manifest;
* SHA-256.

Create a CLI generation command.

At this point, Chaff should already perform a real small generation run.

---

## Phase 3 — Integrity Verification

Implement:

```text
metadata verification
full hash verification
sample verification
reports
```

Complete the critical end-to-end corruption test.

---

## Phase 4 — Rich File Formats

Implement:

```text
EML
DOCX
PDF
XLSX
PPTX
VCF
ICS
```

Validate each with appropriate parser/library tests.

---

## Phase 5 — Storage-Test Features

Implement:

* fill-until-reserve;
* percentage free-space mode;
* large deterministic storage payload;
* continual free-space monitoring;
* generation throughput statistics.

---

## Phase 6 — Safe Cleanup

Implement:

```text
Keep
Delete
Trash
```

Complete containment and destructive-operation safety tests.

---

## Phase 7 — GUI

Build the PySide6 application around the already tested core.

Pages:

```text
Generate
Verify
Runs
ChaffBank
Settings
```

Generation must execute outside the UI thread.

---

## Phase 8 — Packaging

Implement:

* PyInstaller build configuration;
* application icons/resources;
* packaged ChaffBank;
* build documentation.

---

# 84. MVP Completion Criteria

Version 0.1 is not considered complete unless all of the following work:

* GUI starts successfully.
* CLI works without GUI.
* User can select a target.
* User can specify amount.
* User can specify free-space reserve.
* User can select file types.
* User can select a profile.
* User can enter/reuse a seed.
* Chaff creates a unique owned run directory.
* Chaff creates coherent synthetic content.
* TXT generation works.
* EML generation works.
* DOCX generation works.
* PDF generation works.
* XLSX generation works.
* PPTX generation works.
* JSON/CSV/HTML/Markdown generation works.
* Genuine files are produced.
* SHA-256 hashes are recorded.
* Final manifest is generated.
* Full verification detects a changed file.
* Verification detects a deleted file.
* Cleanup cannot delete unrelated files.
* Delete works on a validated Chaff run.
* Trash works where supported.
* Cancellation works.
* Disk-full errors are handled safely.
* UI remains responsive while generating.
* Automated tests pass.
* Documentation describes all major workflows.

---

# 85. Code Quality Rules

Throughout implementation:

1. Prefer small cohesive modules.
2. Avoid god classes.
3. Avoid one giant GUI file.
4. Avoid global mutable state.
5. Avoid UI-specific logic in the core.
6. Avoid hidden random state.
7. Avoid uncontrolled filesystem operations.
8. Use pathlib.
9. Use type annotations.
10. Use enums for controlled states.
11. Validate all external configuration.
12. Use context managers for files.
13. Stream large files.
14. Keep generation deterministic where practical.
15. Fail safely.
16. Never overwrite existing unrelated files.
17. Never silently broaden a cleanup scope.
18. Do not use `eval` or `exec`.
19. Treat custom ChaffBanks as untrusted data.
20. Document architectural decisions that are not obvious.

---

# 86. Agent Working Procedure

Do not attempt to implement the entire application as one giant patch.

Work incrementally.

For each major phase:

1. inspect existing repository state;
2. design interfaces first;
3. implement the smallest coherent unit;
4. add tests;
5. run tests;
6. fix failures;
7. continue to next unit;
8. keep README/docs synchronized.

When architectural decisions change, update:

```text
docs/architecture.md
```

Do not leave placeholder implementations such as:

```python
pass
# TODO implement later
raise NotImplementedError
```

inside functionality claimed as completed.

It is acceptable to explicitly defer a feature to a documented future phase, but completed phases must actually work.

---

# 87. Agent Safety During Development

This project intentionally contains disk-consuming functionality.

While developing or testing:

**DO NOT ACTUALLY FILL THE HOST DRIVE.**

Never execute an unrestricted generation command against:

```text
/
C:\
/home
$HOME
repository parent directories
mounted production storage
```

Use temporary test directories.

Keep automated generation tiny.

Do not assume that because a feature is called "testing" it is safe to run at production scale.

Add safeguards before implementing high-volume generation.

---

# 88. Desired Final Product Experience

The desired workflow should ultimately feel like this:

```text
Open Chaff
        ↓
Choose /media/usb-test
        ↓
Select "Storage Test"
        ↓
Generate until 5 GiB remains
        ↓
Enable:
    TXT
    Email
    DOCX
    PDF
    XLSX
    PPTX
    CSV
    Storage Payload
        ↓
Seed: 827381729
        ↓
Create SHA-256 manifest ✓
        ↓
Completion action: Keep
        ↓
Review preflight estimate
        ↓
Start
```

During generation:

```text
184.2 GiB / 450.0 GiB

Files:
12,481

Current:
Documents/Projects/Northwind Migration/
Quarterly Review Q2 2026.pdf

Filesystem free:
271.8 GiB

Speed:
137 MiB/s
```

After generation:

```text
Generation complete

Generated:
450.0 GiB

Files:
27,182

Manifest:
chaff-manifest.json

[ Verify Now ]
[ Open Folder ]
[ Delete Chaff ]
```

Months later:

```text
Open Chaff
    ↓
Verify
    ↓
Select manifest
    ↓
Full verification
```

Result:

```text
27,182 expected
27,181 intact
1 hash mismatch
0 missing
0 unreadable

Affected:
Documents/Archive/Invoices/Invoice-01842.pdf
```

That ability to create **known synthetic storage and later prove whether it remained intact** is a central identity of the application.

---

# 89. Future Extension Points

Architect cleanly for later additions such as:

* additional languages;
* regional synthetic-data packs;
* image generation;
* audio/video dummy media;
* ZIP/TAR archives;
* SQLite database generation;
* browser-like data;
* application-specific test datasets;
* corrupted-file simulation;
* duplicate-file generation;
* filesystem benchmarking;
* scheduled verification;
* multi-drive testing;
* checksums other than SHA-256;
* BLAKE3 high-speed verification;
* resumable generation;
* generated file age/timestamp distributions;
* user-created custom profiles;
* template-pack export/import;
* command-line automation APIs.

Do not implement all of these now.

Create appropriate extension boundaries so they do not require rewriting the core.

---

# 90. Final Engineering Principle

Chaff Generator is not merely:

> "write random files until a disk is full."

It is:

> **A deterministic synthetic-data corpus generator, filesystem capacity tool, and integrity-verification utility capable of producing coherent collections of genuine everyday computer file formats from reusable data banks and templates.**

Every architectural decision should reinforce that definition.

Build the smallest production-quality version of that system first, then extend it cleanly.

### A few design choices in that prompt are especially important

**1. The manifest changes the value of the application.** Without it, you have a sophisticated dummy-file generator. With it, Chaff becomes a storage verification utility. A generated 2 TB corpus can become a known reference dataset whose state can be checked months later.

**2. The `GenerationWorld` will make the output dramatically better.** Instead of 10,000 unrelated random documents, you get a fictional computer belonging to someone who works for a fictional company, has recurring coworkers and projects, receives related email, produces reports about those projects, and has spreadsheets that refer to the same entities.

**3. The semantic intermediate models solve the multi-format problem.** You should not need five independent "quarterly report" templates for TXT, HTML, PDF, DOCX, and Markdown. One `ProseDocument` can feed five renderers.

**4. Storage-test payloads solve the scale problem.** Normal `.docx` and `.eml` files are often small. Trying to generate 2 TB exclusively from realistic office documents could mean millions of files. A Storage Test profile can generate perhaps thousands of genuine normal files plus larger deterministic payload files to consume the remaining capacity efficiently.

**5. ChaffBank should be treated almost like its own file format.** Eventually you could have `finance-en`, `developer-workstation`, `legal-office`, `medical-demo`, `personal-computer`, or organization-specific synthetic-data packs without modifying Python code. The sandboxed Jinja model is well suited to allowing external packs without letting them execute arbitrary Python. ([Jinja Documentation][2])

**6. `.eml` should be a serious part of the project.** Python already has a full email/MIME object model, and its mailbox module supports formats including Maildir and mbox. That lets Chaff eventually create entire realistic fake mailboxes—not merely loose text files pretending to be messages. ([Python documentation][9])

The result I would aim for is essentially **Faker for complete filesystems**: not just fake names and addresses, but coherent synthetic computers, with reproducibility, capacity controls, and cryptographic integrity checking.

[1]: https://doc.qt.io/qtforpython-6/?utm_source=chatgpt.com "Qt for Python"
[2]: https://jinja.palletsprojects.com/en/stable/sandbox/?utm_source=chatgpt.com "Sandbox — Jinja Documentation (3.1.x)"
[3]: https://typer.tiangolo.com/?utm_source=chatgpt.com "Typer"
[4]: https://docs.python.org/3/library/email.examples.html?utm_source=chatgpt.com "email: Examples"
[5]: https://python-docx.readthedocs.io/?utm_source=chatgpt.com "python-docx — python-docx 1.2.0 documentation"
[6]: https://github.com/arsenetar/send2trash?utm_source=chatgpt.com "GitHub - arsenetar/send2trash: Python library to natively send files to Trash (or Recycle bin) on all platforms. · GitHub"
[7]: https://csrc.nist.gov/pubs/sp/800/88/r2/final?utm_source=chatgpt.com "SP 800-88 Rev. 2, Guidelines for Media Sanitization | CSRC"
[8]: https://www.cyber.gc.ca/en/guidance/it-media-sanitization-itsp40006?utm_source=chatgpt.com "IT media sanitization (ITSP.40.006) - Canadian Centre for Cyber Security"
[9]: https://docs.python.org/3/library/email.message.html?utm_source=chatgpt.com "Representing an email message"

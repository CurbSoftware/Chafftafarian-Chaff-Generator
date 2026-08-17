# Template Reference

Templates are Jinja2 rendered inside a `SandboxedEnvironment` with
`StrictUndefined`: a misspelled variable fails loudly (with a
"did you mean" suggestion) instead of rendering empty output.

Template packs contain **data only** — never Python modules. `import`,
`include`, and `extends` are unavailable.

## Variables (the world)

Every template renders in a context seeded from the run's synthetic world:

| Variable | Type | Example use |
| --- | --- | --- |
| `primary_user` | Person | `{{ primary_user.full_name }}` |
| `organization`, `company` | Organization | `{{ organization.name }}` |
| `project` | Project | `{{ project.name }}` |
| `project_manager` | Person | `{{ project_manager.email }}` |
| `person` | Person (an employee) | `{{ person.full_name }}` |
| `contact` | Contact | `{{ contact.phone }}` |
| `client` | Client | `{{ client.company }}` |
| `vendor` | Vendor | `{{ vendor.name }}` |
| `meeting` | Meeting | `{{ meeting.topic }}` |
| `invoice` | Invoice | `{{ invoice.total }}` |
| `product` | Product | `{{ product.name }}` |

Exactly which entities exist depends on the pack's banks and the run's
volume; guards like `{% if project %}` keep templates portable.

## Helpers

| Helper | Signature | Notes |
| --- | --- | --- |
| `word(category)` | `str` | Random word from a word bank, e.g. `word('technologies')` |
| `pick(sequence)` | value | Random element of a list |
| `sentence(domain)` | `str` | A sentence from the sentence banks (`business`, `personal`, …) |
| `paragraph(domain)` | `str` | Several sentences |
| `integer(min, max)` | `int` | Inclusive |
| `decimal(min, max, places)` | `Decimal` | Never float — no representation drift |
| `money(min, max)` | `Decimal` | Currency-scale decimal |
| `date_recent(days)` | `date` | Within the last N days of the run's window |
| `date_between(start, end)` | `date` | Inside the run's configured date range |
| `uuid()` | `str` | UUID4-shaped, seeded |
| `email_address(person)` | `str` | Always a reserved domain (`@example.com` / `@<org>.example`) |
| `phone_number()` | `str` | Formatted, seeded |

## Filters

| Filter | Example | Result |
| --- | --- | --- |
| `slug` | `{{ project.name \| slug }}` | `atlas-migration` |
| `currency` | `{{ invoice.total \| currency }}` | `$12,345.67` |
| `datefmt` | `{{ meeting.date \| datefmt }}` | `2025-03-14` |

## Errors

A template that references an unknown variable aborts the render with a
`TemplateError` that names the template and suggests the closest known
name:

```text
Unknown variable: 'project.owner_nme' — did you mean 'project.owner_name'?
```

The GUI's ChaffBank page (Template preview) and `chaff packs validate`
surface these errors before a run ever writes a file.

## Writing templates

Templates live in a pack under `templates/<kind>/*.yaml`, where *kind* is
one of `prose`, `email`, `tabular`, `presentation`, `record`, `calendar`,
`contact`. Each YAML file carries an id, the kind, a validated per-kind
body schema, and optional description/domains metadata. Validate a pack
with `chaff packs validate <path>`; preview with the GUI or a tiny seeded
run.

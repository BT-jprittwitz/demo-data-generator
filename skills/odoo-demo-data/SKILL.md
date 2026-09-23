---
name: odoo-demo-data
description: Use when creating, extending, generating or testing an Odoo demo-data module (ZIP) for a customer - trigger words "Demo-Daten", "Demo-Paket", "Kunde X", a new customer JSON spec, a new Odoo object type/model (CRM, Purchasing, Inventory, Accounting, Helpdesk, ...), or installing a generated bt_demo_* module for verification. Covers the generator CLI, the customer spec format, verified Odoo 19.0 patterns and the real install smoke test.
---

# Odoo Demo-Data Generator

Builds an installable Odoo 19.0 module (ZIP) from a customer specification (JSON).
Pure Python stdlib, no `pip install`. This skill is the entry point; the detailed
knowledge lives in `reference/`.

## When to use this skill

- Create a new demo package for a customer.
- Extend an existing specification (new products, new object type).
- Add a new Odoo object type/field -> **first**
  `reference/verification-protocol.md`.
- Test a generated module against a real Odoo kernel ->
  `reference/install-test-protocol.md`.

## Hard rules (non-negotiable)

1. **Never guess Odoo field names or behavior.** Verify against the real Odoo 19.0
   source before any XML generation. Source and procedure:
   `reference/verification-protocol.md`.
2. **On an installation error: read the complete traceback** before attempting a
   fix. No fix without a traceback.
3. **No `--test-enable`** for the installation smoke test.
4. Language: docs, skills and code comments are English. Generated demo-data text
   follows the example company's country (spec field `language` overrides) - see
   `reference/verified-patterns.md` 4.16 and `reference/spec-format.md`.

## Workflow (customer -> module)

1. **Determine the required bundles.** Research the customer's industry/business
   model and reason about which processes matter - including adjacent ones (e.g.
   medical devices -> quality control, batch/lot traceability). Then pick
   capability bundles from `reference/capabilities.md` (menu with "relevant when"
   hints; live via `python3 -m engine.cli capabilities`). Dependencies are closed
   automatically (e.g. `mrp` pulls the warehouse and the product catalog). There is
   **no fixed industry profile** (`ROADMAP.md`, principle "No fixed industry
   verticals"). Section/field details: `reference/spec-format.md`.
2. **Write the specification.** Scaffold it from the chosen bundles (recommended,
   closes dependencies):
   ```bash
   python3 -m engine.cli new --with <bundle,...> --name "<Customer>" --country ch \
       [--street/--city/--zip/--vat/--currency/--chart-template] --out examples/<customer>.json
   ```
   Then fill the sections with real content. Either example spec also works as a
   template: `examples/muster_foerdertechnik.json` (manufacturing) or
   `examples/muster_handel.json` (multi-app/Enterprise). All fields:
   `reference/spec-format.md`. Aim for the recommended "rich demo" volume per
   used section (`reference/spec-format.md`, "Recommended data volume") - the
   generator warns below it.
3. **Generate** (static validation runs automatically, no ZIP is built on errors):
   ```bash
   python3 -m engine.cli generate --spec examples/<customer>.json --out output
   ```
4. **Validate statically** (optional, independent of the build):
   ```bash
   python3 -m engine.cli validate output/<technical_name>.zip
   ```
5. **Install for real** against Odoo 19.0 and cross-check via Postgres:
   `reference/install-test-protocol.md`.
6. **Deliver.** Formalities (name, author, license), company scoping, ZIP:
   `reference/delivery.md`.

## Engine overview

```
engine/
  model.py         dataclasses of the spec + validation of the spec itself
  spec_loader.py   JSON -> dataclasses
  records.py       dataclasses -> Odoo XML (the verified patterns)
  manifest.py      __manifest__.py / hooks.py (company visibility, invoice posting)
  builder.py       module directory + ZIP
  validate.py      static check of the known landmines (no Odoo needed)
  volume.py        recommended minimum demo-data volume per object type
  verify.py        spec-aware Postgres assertions for the install smoke test
  cli.py           CLI (generate / validate)
examples/          example specifications
engine/tests/      engine tests:  python3 -m unittest discover -s engine/tests -t .
engine/docker/     installation smoke-test harness, Enterprise instance ../odoodemo-local (see engine/docker/README.md)
examples/reference/  historical reference modules (no longer a template)
```

## Core principles (resilience)

- **Executable beats prose:** Every known landmine has a rule in
  `engine/validate.py` and a test. Add new findings there first + in
  `reference/verified-patterns.md`, not just as prose.
- **Single source of truth:** A rule exactly once. Reference files point to
  code/tests instead of duplicating.
- **Demand-driven growth:** A new object type only appears once a concrete
  customer needs it - but then fully verified + tested.
- **No fixed industry verticals:** no catalog of canned industry profiles; each
  module is composed per customer from the verified building blocks. Rationale:
  `ROADMAP.md`.
- **Test for real instead of guessing:** Static validation does not replace a real
  installation.

## Reference files

| File | Content |
|---|---|
| `reference/verified-patterns.md` | All verified Odoo 19.0 patterns (fields, sources, landmines) |
| `reference/spec-format.md` | Complete JSON schema of the customer specification |
| `reference/capabilities.md` | Capability bundles (selection menu, "relevant when", dependencies) - generated |
| `reference/verification-protocol.md` | How to verify a new object type/field against the source |
| `reference/install-test-protocol.md` | Real installation smoke test (Enterprise, fresh DB, Postgres) |
| `reference/delivery.md` | Formalities, company scoping, history of the delivered modules |

---
description: Create a new Odoo demo-data package for a customer
agent: build
---

Create a new Odoo demo-data package for the following customer: $ARGUMENTS

Load and follow the `odoo-demo-data` skill (`skills/odoo-demo-data/SKILL.md`) and
the reference files it points to. Steps:

1. Research the customer (industry/business model). Reason about which processes
   matter - including adjacent apps (e.g. medical devices -> quality control).
   Pick capability bundles per `skills/odoo-demo-data/reference/capabilities.md`
   (`python3 -m engine.cli capabilities`); dependencies are closed automatically.
   If the reasoning needs an app without a bundle, say so explicitly (demand
   signal) instead of faking data. Determine the demo-data language: derive it
   from the company country unless the user names a language explicitly
   (e.g. an English-only IT lead).
2. Create a new spec under `examples/<customer>.json`, based on
   `examples/nishcom_ag.json`; format per `reference/spec-format.md`.
3. Build: `python3 -m engine.cli generate --spec examples/<customer>.json --out output`.
4. Run the real install smoke test per `reference/install-test-protocol.md`
   (fresh DB, no `--test-enable`, Postgres cross-check).
5. On an install error: read the full traceback first, then fix. Never guess Odoo
   field names - verify new object types against the 19.0 source per
   `reference/verification-protocol.md`.

Summarise at the end: files created, verified installation, open points.

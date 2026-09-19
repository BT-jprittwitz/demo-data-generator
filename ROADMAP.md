# Roadmap / open items

Principle: **demand-driven growth.** A new object type, a new archetype or a new
app is only built once a concrete customer needs it - but then fully verified
(see `skills/odoo-demo-data/reference/verification-protocol.md`) and tested.

## End goal

One call with the customer name is enough: research of industry/size/
business model, derivation of the matching demo-data profile, generation and
delivery of the module - minimal friction.

## Achieved

- Generator engine (JSON spec -> installable Odoo 19.0 module ZIP).
- Verified building blocks: company (incl. chart of accounts), partners, products,
  bills of materials, sales, CRM, purchasing, inventory, accounting (posted invoices),
  helpdesk. Two reference specs (manufacturing, multi-app/Enterprise).
- Static validation of the known landmines + tests; real
  installation procedure against Enterprise 19.0 documented.
- Knowledge as a neutral skill (`skills/odoo-demo-data/`) instead of handover prose.

## Open

- **Web research automation:** Automatically derive industry/size/business model
  from a customer name and determine the demo-data profile from it.
  Prerequisite for the end-goal workflow.
- **`engine/docker/test_install.py`:** Run installation automatically (fresh DB per
  run, scan log for `Traceback`/`CRITICAL`/`ERROR`, drop DB on success).
  Sketched in `engine/docker/README.md`.
- **Multi-user visibility:** possibly extend `post_init_hook` to several/all relevant
  users instead of only `base.user_admin`.
- **SaaS archetype** (subscriptions, maintenance products) - conceptually named,
  not implemented.
- **More object types/apps** depending on customer demand (e.g. projects, manufacturing).

## Deliberately out of scope

- **Manufacturing orders (`mrp.production`):** `picking_type_id` depends on the
  target instance's warehouse setup (same dependency class as
  chart-of-accounts references).
- **Website/E-commerce (`website_sale`):** the shop filters by `website.company_id`;
  collides with the goal of an own demo company. Needs separate clarification.

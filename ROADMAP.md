# Roadmap / open items

Principles:

- **Demand-driven growth.** A new object type or a new app is only built once a
  concrete customer needs it - but then fully verified (see
  `skills/odoo-demo-data/reference/verification-protocol.md`) and tested.
- **No fixed industry verticals.** There is deliberately **no catalog of canned
  industry profiles** (manufacturing, retail, SaaS, ...): example customers differ
  too much. Research determines which Odoo apps, process chain and object types a
  customer actually needs; the module is composed per customer from the verified
  building blocks (the sections in `engine/model.py`). Reusable "profiles" exist
  only as these building blocks, never as industry presets.

## End goal

One call with the customer name is enough: research of industry/size/
business model, derivation of the required Odoo apps and object types
(per-customer composition, no fixed industry profile), generation and delivery of
the module - minimal friction.

## Achieved

- Generator engine (JSON spec -> installable Odoo 19.0 module ZIP).
- Verified building blocks: company (incl. chart of accounts), partners, products,
  bills of materials, manufacturing orders (draft; implies the warehouse),
  sales, CRM, purchasing, inventory, accounting (posted invoices), helpdesk.
  Two reference specs (manufacturing, multi-app/Enterprise).
- Static validation of the known landmines + tests; real
  installation procedure against Enterprise 19.0 documented.
- `engine/docker/test_install.py`: automated installation smoke test against the
  local Enterprise instance (`../odoodemo-local`) - fresh DB per run, log analysis,
  full log on failure.
- Knowledge as a neutral skill (`skills/odoo-demo-data/`) instead of handover prose.
- Auto-created demo login (`demo`/`demo`, name = company) with the same
  groups/companies as `base.user_admin` - no manual user setup after a demo
  appointment (verified-patterns.md 4.18). Existing login is skipped, not fatal.

## Open

- **Web research automation:** Automatically derive industry/size/business model
  from a customer name and, from it, the required apps, process chain and object
  types (per-customer composition, no fixed verticals - see the principles above).
  Prerequisite for the end-goal workflow.
- **Multi-user visibility:** possibly extend `post_init_hook` to several/all relevant
  users instead of only `base.user_admin`. (An auto-created demo user with the
  company name and admin rights already exists, see "Achieved" - this item is
  about *more* users, not the single demo login.)
- **Subscription/SaaS building blocks** (subscriptions, maintenance products) -
  conceptually named, not implemented; only built when a concrete customer needs
  them, and then as building blocks, not as a fixed vertical.
- **More object types/apps** depending on customer demand (e.g. projects, manufacturing).

## Deliberately out of scope

- **Website/E-commerce (`website_sale`):** the shop filters by `website.company_id`;
  collides with the goal of an own demo company. Needs separate clarification.

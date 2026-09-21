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

## Version / branch strategy

- **`19.0`** (renamed from `main`): the verified Odoo **19.0** line - generator
  engine plus the Enterprise install smoke-test harness. This is what delivered
  demo packages are built and tested against today; kept stable, changes only as
  fixes/backports.
- **`20.0`** (branched from `19.0`): the new development trunk for Odoo **20**.
  First step is the install smoke-test harness against a local Odoo 20 instance;
  the verified patterns are ported/verified against the Odoo 20 source afterwards.
  Intended as the GitHub default branch once the harness runs.

## End goal

One call with the customer name is enough: research of industry/size/
business model, derivation of the required Odoo apps and object types
(per-customer composition, no fixed industry profile), generation and delivery of
the module - minimal friction.

## Achieved

- Generator engine (JSON spec -> installable Odoo 19.0 module ZIP) on the `19.0`
  branch.
- Verified building blocks: company (incl. chart of accounts), partners, products,
  bills of materials, manufacturing orders (draft; implies the warehouse),
  sales (incl. quotation templates `sale.order.template`), CRM, purchasing,
  inventory, accounting (posted invoices), helpdesk, projects
  (`project.project` + `project.task` + task stages), maintenance
  (`maintenance.equipment`/`request`), quality control (`quality.point`/`check`/
  `alert`), subscriptions (`sale.order` + `plan_id`) and field service
  (`project.is_fsm`).
  Reference specs: manufacturing, multi-app/Enterprise, German IT system house
  `de_skr04`, German CHP manufacturer `enertec`.
- Static validation of the known landmines + tests; real
  installation procedure against Enterprise 19.0 documented.
- `engine/docker/test_install.py`: automated installation smoke test against the
  local Enterprise instance (`../odoodemo-local`) - fresh DB per run, log analysis,
  full log on failure, plus spec-aware Postgres data assertions (record counts via
  `ir_model_data`, invoice posting, `standard_price` company key) so a swallowed
  `post_init_hook` error cannot pass as success.
- Knowledge as a neutral skill (`skills/odoo-demo-data/`) instead of handover prose.
- Auto-created demo login (`demo`/`demo`, name = company) with the same
  groups/companies as `base.user_admin` - no manual user setup after a demo
  appointment (verified-patterns.md 4.18). Existing login is skipped, not fatal.

## Open

- **Odoo 20 support (`20.0` branch):** stand up the install smoke-test harness
  against a local Odoo 20 Enterprise instance (`../odoodemo-local-20`, parallel to
  the 19.0 instance), then verify/adjust the Odoo 19.0 patterns against the Odoo
  20 source (`skills/odoo-demo-data/reference/verification-protocol.md`) and run
  the reference specs through the harness. Trigger: Odoo 20 availability + first
  customer on 20.
- **Web research automation:** Automatically derive industry/size/business model
  from a customer name and, from it, the required apps, process chain and object
  types (per-customer composition, no fixed verticals - see the principles above).
  Prerequisite for the end-goal workflow.
- **Multi-user visibility:** possibly extend `post_init_hook` to several/all relevant
  users instead of only `base.user_admin`. (An auto-created demo user with the
  company name and admin rights already exists, see "Achieved" - this item is
  about *more* users, not the single demo login.)
- **More object types/apps** depending on customer demand - only with a concrete
  customer, then verified + tested (e.g. approvals, timesheets, e-commerce).

## Deliberately out of scope

- **Website/E-commerce (`website_sale`):** the shop filters by `website.company_id`;
  collides with the goal of an own demo company. Needs separate clarification.

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

- **`20.0`**: the development trunk for Odoo **20** - generator engine plus the
  Enterprise install smoke-test harness (`../odoodemo-local-20`). This is what
  delivered demo packages are built and tested against today.
- **`main`**: the repository's default branch. It still points at the `19.0` line;
  once the `20.0` migration is merged (branch-strategy step, not done yet) it will
  fast-forward to `20.0`.
- **`19.0`**: the previous verified Odoo **19.0** line, kept stable (changes only
  as fixes/backports). Its local instance is `../odoodemo-local`.

## End goal

One call with the customer name is enough: research of industry/size/
business model, derivation of the required Odoo apps and object types
(per-customer composition, no fixed industry profile), generation and delivery of
the module - minimal friction.

## Achieved

- Generator engine (JSON spec -> installable Odoo 20.0 module ZIP) on the `20.0`
  branch (previously 19.0 on `19.0`).
- Verified building blocks: company (incl. chart of accounts), partners, products,
  bills of materials, manufacturing orders (draft; implies the warehouse),
  sales (incl. quotation templates `sale.order.template`), CRM, purchasing,
  inventory, accounting (posted invoices), helpdesk, projects
  (`project.project` + `project.task` + task stages), maintenance
  (`maintenance.equipment`/`request`), quality control (`quality.point`/`check`/
  `alert`) and subscriptions (`sale.order` + `plan_id`).
  Reference specs: manufacturing, multi-app/Enterprise, German IT system house
  `de_skr04`, German CHP manufacturer `Musterkraft`, Austrian gas-technology
  manufacturer `bt_demo_gastechnik` (first `l10n_at` chart).
- Static validation of the known landmines + tests; real
  installation procedure against Enterprise 20.0 documented.
- `engine/docker/test_install.py`: automated installation smoke test against the
  local Enterprise instance (`../odoodemo-local-20`) - fresh DB per run, log
  analysis, full log on failure, plus spec-aware Postgres data assertions (record
  counts via `ir_model_data`, invoice posting, `standard_price` company key) so a
  swallowed `post_init_hook` error cannot pass as success.
- Knowledge as a neutral skill (`skills/odoo-demo-data/`) instead of handover prose.
- Auto-created demo login (`demo`/`demo`, name = company) with the same
  groups/companies as `base.user_admin` - no manual user setup after a demo
  appointment (verified-patterns.md 4.18). Existing login is skipped, not fatal.

## Open

- **Odoo 20 support (`20.0` branch) - done:** the install smoke-test harness runs
  against a local Odoo 20 Enterprise instance (`../odoodemo-local-20`); all
  committed reference specs (`muster_foerdertechnik`, `muster_handel`, `muster_it`,
  `muster_kraftwerke`) install cleanly with green Postgres assertions.
  - **Note:** there is no official `odoo:20.0` Docker image, so the instance is
    built from source on top of the `odoo:19.0` base image (arm64, Python 3.12) -
    see `../odoodemo-local-20/Dockerfile`.
  - **Community-core deltas verified against `odoo/odoo@20.0`:** `base_vat` gone
    (VAT always validated, verified-pattern 4.19); `product_uom_id` -> `uom_id` on
    `mrp.production` / `mrp.bom` / `mrp.bom.line` / `purchase.order.line`;
    `maintenance.request.request_date` removed; `quality.alert.product_tmpl_id`
    removed; declarative `models.Constraint(...)`; a project now auto-creates
    default task stages.
  - **Enterprise-20 verified:** helpdesk 4.14, quality 4.23/4.24 and subscriptions
    4.25 hold; **Field Service 4.26 is obsolete** (see below).
- **Field Service on 20.0:** `industry_fsm` and `project.is_fsm` were removed and
  the app was re-implemented on `planning` (`planning_field_service`,
  `planning.slot`). The `field_service` bundle and the `Project.is_fsm` spec field
  were dropped; rebuilding it needs a new `planning.slot` building block
  (demand-driven) - not started.
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
  Concrete demand signals so far: the **`appointment`** app (booking of
  treatment slots, from the Swiss podology practice `bt_demo_musterpodologie`).

## Deliberately out of scope

- **Website/E-commerce (`website_sale`):** the shop filters by `website.company_id`;
  collides with the goal of an own demo company. Needs separate clarification.

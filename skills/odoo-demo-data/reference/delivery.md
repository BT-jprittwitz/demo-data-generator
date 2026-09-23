# Delivery: formalities, company scoping, history

## Formalities

- **Technical name** keep short, e.g. `bt_demo_mfg`, `bt_demo_musterhandel`.
- **Author:** always `braintec`.
- **License:** `LGPL-3`.
- **Website:** `https://www.braintec.com`.
- Output: `output/<technical_name>/` (module directory) and
  `output/<technical_name>.zip` (the delivered artifact). `output/` is gitignored.

## Company scoping (central)

Target instances often already contain a different demo-data package. Therefore
every package creates its **own `res.company`** (customer name, address, real
data where possible) and keys **all** demo data to it:

- Partners, products, sales orders, purchasing, inventory, CRM, helpdesk: `company_id` =
  demo company.
- Invoices: `company_id` + `context="{'allowed_company_ids': [...]}"`.
- The `post_init_hook` adds `base.user_admin` to the demo company's
  `company_ids` (otherwise invisible, see verified-patterns 4.5).
- The `post_init_hook` also creates a demo login (`demo`/`demo`, name = company)
  with the same groups/companies as `base.user_admin`, so the customer can log in
  after the appointment without a manual user setup (verified-patterns 4.18). If
  the login already exists, creation is skipped.
- E-commerce/website would need separate clarification (the shop filters by
  `website.company_id`); currently **not** covered.

## Deliberately out of scope

- **Invoices/accounting**: supported in the meantime (with chart-of-accounts
  loading and `accounting_app`), but only with an installable localization.

## History of the delivered modules

1. `bt_demo_example_skr04.zip` — first PoC (SKR04, invoices). **Superseded.**
2. `bt_demo_example_manufacturing.zip` — manufacturing PoC. **Buggy** (double record
   product.template/product.product; `state='sale'`). Do not use.
3. `bt_demo_mfg.zip` — installable, company-visibility fix. **Buggy**
   (`standard_price` without company context). Kept as a historical reference under
   `examples/reference/bt_demo_mfg.zip`; no longer use as a template.
4. Generator engine in this repo. `examples/muster_foerdertechnik.json`
   reproduces the same customer as (3), fixes the bug and adds
   master-data depth.
5. `bt_demo_musterhandel` (`examples/muster_handel.json`) — first multi-app/Enterprise case:
   company + chart of accounts `ch`, product range, CRM, purchasing, inventory, posted
   customer/vendor invoices, helpdesk. Verified against Enterprise 19.0.
6. `bt_demo_muster_it` (`examples/muster_it.json`) — German IT system house
   (Muster IT-Solutions GmbH, Unterschreissheim): first `de_skr04` chart of
   accounts, hardware + IT-service catalog, CRM, purchasing, inventory, posted
   invoices/bills, helpdesk. Verified against Enterprise 19.0. New landmine
   found and documented: partner VAT checksum validation via `base_vat`
   (pulled in by `l10n_de`, verified-patterns.md 4.19).
7. Same `bt_demo_muster_it` extended with the new building blocks
   **quotation templates** (`sale.order.template`, "Angebotsvorlagen") and
   **projects** (`project.project` + `project.task` + task stages). Verified
   against Enterprise 19.0 and by the spec-aware Postgres assertions of the
   smoke test (see `install-test-protocol.md`). New verified patterns 4.20/4.21.
8. `bt_demo_musterkraftwerke` (`examples/muster_kraftwerke.json`) — German manufacturer
   of made-to-measure combined heat and power plants (Musterkraftwerke GmbH,
   Musterstadt/Thuringia): `de_skr04` chart of accounts, component + finished-goods
   catalog, bills of materials and draft manufacturing orders, purchasing, stock,
   CRM pipeline, project delivery (planning -> fabrication -> installation ->
   commissioning), posted customer/vendor invoices and after-sales service
   tickets. Bundles: `mrp`, `purchase`, `sales`, `crm`, `project`, `accounting`,
   `helpdesk`. Verified against Enterprise 19.0 including the spec-aware Postgres
   assertions. Open demand signals at the time: `maintenance`, quality control
   (ISO 9001 / TÜV), recurring service revenue (`sale_subscription`) and field
   service.
9. Same `bt_demo_musterkraftwerke` extended with the four former demand signals as new
   building blocks (verified-patterns 4.22-4.26):
   **maintenance** (Community: equipment categories/equipment/requests, demo
   `maintenance.team`), **quality control** (Enterprise `quality_control`:
   `quality.point`/`check`/`alert`), **subscriptions** (Enterprise
   `sale_subscription`: `sale.order` + `plan_id` + recurring products) and
   **field service** (Enterprise `industry_fsm`: `project.is_fsm`). Verified
   against Enterprise 19.0 and by the spec-aware Postgres assertions (including
   `subscriptions_with_plan` and `products_recurring_invoice`). New landmine
   found and documented: a recurring product on a non-draft `sale.order` raises
   `_constraint_subscription_plan` (verified-patterns 4.25).

10. `bt_demo_musterpodologie` (`examples/muster_podologie.json`) — Swiss podology
    practice (medical foot care) and foot-care retailer Muster Podologie AG (Musterstadt
    BL, shops in Basel and Zuerich): `ch` chart of accounts, service + product
    catalog, CRM pipeline, purchasing, inventory, posted invoices/bills, patient
    support tickets, maintenance of practice equipment and recurring foot-care
    subscriptions. Bundles: `sales`, `crm`, `purchase`, `stock`, `accounting`,
    `helpdesk`, `maintenance`, `subscriptions`. Deliberately **no** `quality`/
    `mrp` (the company neither manufactures nor needs batch traceability; its
    medical-device obligations surface as equipment maintenance). Open demand
    signal: the `appointment` app (booking of treatment slots) has no bundle yet.
    Verified against Enterprise 19.0 including the spec-aware Postgres assertions.

11. `bt_demo_gastechnik` — Austrian gas-technology manufacturer (Korneuburg, Lower
    Austria): components and complete plants for the energy transition (landfill
    gas/biogas plants, gas flares, gas compressors, pressure booster stations,
    membrane-based biogas upgrading). First `at`/`l10n_at` chart of accounts
    (Einheitskontenrahmen) and, with it, the first Austrian VAT numbers
    (checksum-valid `ATU...`, `base_vat` pulled in by `l10n_at`). Bundles: `mrp`,
    `purchase`, `sales`, `crm`, `project`, `field_service`, `accounting`,
    `helpdesk`, `maintenance`, `quality`, `subscriptions`. Component/finished-goods
    catalog, 6 BOMs, draft manufacturing orders, procurement, stock, CRM pipeline,
    turnkey-plant delivery projects (incl. a Field Service project), posted
    customer/vendor invoices, after-sales tickets, delivered-plant maintenance,
    quality control points/checks/alerts (gas-tightness, electrical safety,
    membrane performance) and recurring service contracts. New engine capability:
    `at` -> `l10n_at` in `CHART_TEMPLATE_MODULE` (engine/manifest.py, same
    verified pattern as `ch`/`de_*`, verified-patterns.md 4.11). Verified against
    Enterprise 19.0 including the spec-aware Postgres assertions.

12. Odoo 20 migration (`20.0` branch): the generator now targets Odoo 20 and is
    verified against Enterprise 20.0 (`../odoodemo-local-20`, built from source
    since no official `odoo:20.0` image exists). All committed reference specs
    install cleanly with green Postgres assertions. Ported/verified deltas:
    `base_vat` removed (VAT is now always validated - several invented VAT numbers
    in the examples had to be corrected), `product_uom_id` -> `uom_id` on
    `mrp.production`/`mrp.bom`/`mrp.bom.line`/`purchase.order.line`,
    `maintenance.request.request_date` removed, `quality.alert.product_tmpl_id`
    removed. Field Service (`industry_fsm`/`project.is_fsm`) is obsolete in 20.0
    and was dropped. See verified-patterns.md 4.10, 4.17, 4.19-4.26.

## Reference material

The structural model was a colleague's module (Felix Schubert) for
DE accounting demo data (SKR04): `demo_v19_data_skr04_clean/` and
`l10n_de_skr04_demo_assets_loans/`. Used only as a structural model, not
adopted.

# Delivery: formalities, company scoping, history

## Formalities

- **Technical name** keep short, e.g. `bt_demo_mfg`, `bt_demo_nishcom`.
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
5. `bt_demo_nishcom` (`examples/nishcom_ag.json`) — first multi-app/Enterprise case:
   company + chart of accounts `ch`, product range, CRM, purchasing, inventory, posted
   customer/vendor invoices, helpdesk. Verified against Enterprise 19.0.
6. `bt_demo_hold_spada` (`examples/hold_spada.json`) — German IT system house
   (HOLD & SPADA IT-Solutions GmbH, Unterschreissheim): first `de_skr04` chart of
   accounts, hardware + IT-service catalog, CRM, purchasing, inventory, posted
   invoices/bills, helpdesk. Verified against Enterprise 19.0. New landmine
   found and documented: partner VAT checksum validation via `base_vat`
   (pulled in by `l10n_de`, verified-patterns.md 4.19).
7. Same `bt_demo_hold_spada` extended with the new building blocks
   **quotation templates** (`sale.order.template`, "Angebotsvorlagen") and
   **projects** (`project.project` + `project.task` + task stages). Verified
   against Enterprise 19.0 and by the spec-aware Postgres assertions of the
   smoke test (see `install-test-protocol.md`). New verified patterns 4.20/4.21.

## Reference material

The structural model was a colleague's module (Felix Schubert) for
DE accounting demo data (SKR04): `demo_v19_data_skr04_clean/` and
`l10n_de_skr04_demo_assets_loans/`. Used only as a structural model, not
adopted.

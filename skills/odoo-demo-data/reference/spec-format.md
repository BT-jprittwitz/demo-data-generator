# Specification format (customer JSON)

A customer specification is a JSON file that `engine.spec_loader.load_spec`
loads into dataclasses (`engine/model.py`) and validates. Template:
`examples/muster_foerdertechnik.json` (manufacturing) or
`examples/nishcom_ag.json` (multi-app/Enterprise).

All object types are optional; only `module` and `company` are required.
References between records use `xml_id` (module-local, without a dot).
Foreign xmlids (e.g. `base.ch`, `crm.stage_lead1`) are emitted 1:1 as `ref`.

## Top level

```jsonc
{
  "module": { ... },              // required
  "company": { ... },             // required
  "language": "de_CH",            // optional; derived from company country if absent (4.16)
  "crm_team_name": "Vertrieb",    // optional; language-dependent default if absent
  "helpdesk_team_name": "Kundendienst", // optional; language-dependent default
  "accounting_app": "full",       // "full" (account_accountant, Enterprise) | "invoicing"
  "partners": [ ... ],
  "products": [ ... ],
  "boms": [ ... ],
  "crm_leads": [ ... ],
  "purchase_orders": [ ... ],
  "stock_quants": [ ... ],
  "invoices": [ ... ],
  "helpdesk_tickets": [ ... ],
  "quotation": { ... },           // one quotation/sales-order template
  "example_orders": [ ... ]       // example sales orders
}
```

## `module`

| Field | Required | Note |
|---|---|---|
| `technical_name` | yes | Short, e.g. `bt_demo_nishcom`. Yields module folder/zip. |
| `title` | yes | Display name. |
| `summary` | yes | One sentence. |
| `description` | no | Longer text. |
| `category` | no | Default `Sales`. |

## `company`

| Field | Required | Note |
|---|---|---|
| `name`, `street`, `city`, `zip`, `country_xmlid` | yes | Address; `country_xmlid` e.g. `base.ch`. |
| `xml_id` | no | Default `demo_company`. |
| `vat`, `currency_xmlid` | no | e.g. `CHE-142.028.625`, `base.CHF`. |
| `chart_template` | no | E.g. `ch` (loads the l10n_ch chart of accounts, see verified-patterns 4.11). |

Without `chart_template` no chart of accounts is loaded; invoices need it.

## `partners[]`

| Field | Required | Default |
|---|---|---|
| `xml_id`, `name`, `country_xmlid`, `street`, `city`, `zip` | yes | |
| `vat` | no | |
| `is_company` | no | `true` |
| `supplier_rank` | no | `0` (vendor -> `1`) |
| `customer_rank` | no | `1` |

## `products[]`

| Field | Required | Note |
|---|---|---|
| `xml_id`, `name`, `type`, `sale_ok`, `purchase_ok` | yes | `type`: `consu` or `service`. |
| `list_price` | no | Sales price (not company_dependent). |
| `standard_price` | no | Cost price (company_dependent -> context automatic). |
| `is_storable` | no | Default: `type == "consu"`. |
| `default_code`, `barcode`, `weight`, `volume`, `description_sale` | no | Barcodes must be unique. |

## `boms[]` (manufacturing customer)

`xml_id`, `product_xmlid`, `lines[]` with `product_xmlid`, `qty`,
optional `uom_xmlid` (default `uom.product_uom_unit`); optional `qty`/`uom_xmlid`
on the BOM itself.

## `crm_leads[]`

`xml_id`, `name` (required); `type` default `opportunity`; `partner_xmlid`,
`contact_name`, `email_from`, `phone`, `expected_revenue`, `probability`,
`stage_xmlid` (default `crm.stage_lead1`), `description`, `priority`.
Stages `crm.stage_lead1`..`lead3` (not `lead4`, which is `is_won`).

## `purchase_orders[]`

`xml_id`, `partner_xmlid`, `lines[]` (required); `state` default `draft`,
`date_order`, `partner_ref`. Line: `product_xmlid`, `qty`, `price_unit`,
`description`; optional `date_planned`.
`state` only `draft`/`sent` (see verified-patterns 4.10).

## `stock_quants[]`

`product_xmlid`, `qty`. Sets `quantity` (no stock move). Forces a demo
`stock.warehouse`; products should be `is_storable`.

## `invoices[]`

`xml_id`, `move_type` (`out_invoice` | `in_invoice`), `partner_xmlid`,
`invoice_date`, `lines[]` (required); optional `ref`.
Line: `product_xmlid`, `qty`, `price_unit`, `description`.
Created as `draft` and posted in the `post_init_hook` (requires
`chart_template`).

## `helpdesk_tickets[]` (Enterprise)

`xml_id`, `name` (required); `partner_xmlid`, `stage_xmlid`
(default `helpdesk.stage_new`), `priority`, `description`.
The partner must belong to the demo company.

## `quotation` / `example_orders[]`

`xml_id`, `partner_xmlid`, `lines[]` with `product_xmlid`, `qty`, `description`;
`state` default `sent` (only `draft`/`sent`), optional `date_order`.
`quotation` is written without, `example_orders` with `noupdate`.

## What static validation rejects

`engine/validate.py` + `engine/model.py` enforce among other things: unknown
`product.type`, unsafe `sale.order` states, unsafe `purchase.order` state,
`account.move` with `state`, `stock.quant` with `inventory_quantity`,
`standard_price` without company context, duplicate barcodes, dangling
`xml_id` references, missing manifest files.

# Specification format (customer JSON)

A customer specification is a JSON file that `engine.spec_loader.load_spec`
loads into dataclasses (`engine/model.py`) and validates. Template:
`examples/muster_foerdertechnik.json` (manufacturing) or
`examples/muster_handel.json` (multi-app/Enterprise).

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
  "customer_profile": { ... },    // optional; business reasoning + relatability check
  "partners": [ ... ],
  "products": [ ... ],
  "boms": [ ... ],
  "crm_leads": [ ... ],
  "purchase_orders": [ ... ],
  "stock_quants": [ ... ],
  "invoices": [ ... ],
  "helpdesk_tickets": [ ... ],
  "quotation": { ... },           // one draft quotation (sale.order)
  "quotation_templates": [ ... ], // reusable sale.order.template ("Angebotsvorlagen")
  "example_orders": [ ... ],      // example sales orders
  "projects": [ ... ],            // project.project
  "project_task_stages": [ ... ], // project.task.type (task stages)
  "project_tasks": [ ... ],       // project.task
  "maintenance_equipment_categories": [ ... ], // maintenance.equipment.category
  "maintenance_equipment": [ ... ],            // maintenance.equipment
  "maintenance_requests": [ ... ],             // maintenance.request
  "quality_points": [ ... ],      // quality.point
  "quality_checks": [ ... ],      // quality.check
  "quality_alerts": [ ... ],      // quality.alert
  "subscriptions": [ ... ]        // sale.order with plan_id
}
```

## `module`

| Field | Required | Note |
|---|---|---|
| `technical_name` | yes | Short, e.g. `bt_demo_musterhandel`. Yields module folder/zip. |
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
| `recurring_invoice` | no | Marks a subscription product (`sale_subscription` only, verified-patterns 4.25). Requires the `subscriptions` bundle; a recurring product on a non-draft sale order is rejected. |

## `boms[]` (manufacturing customer)

`xml_id`, `product_xmlid`, `lines[]` with `product_xmlid`, `qty`,
optional `uom_xmlid` (default `uom.product_uom_unit`); optional `qty`/`uom_xmlid`
on the BOM itself.

## `manufacturing_orders[]` (manufacturing customer)

`xml_id`, `product_xmlid`, `qty` (> 0) (required); optional `bom_xmlid` (else
computed from the product), `date_start`. Created as `draft`; `state` is computed
in Odoo and never set. Requires `boms` and forces the demo `stock.warehouse`
(the manufacturing operation type provides `picking_type_id`). Manufacturing
implies inventory, never the reverse. See verified-patterns 4.17.

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

## `quotation_templates[]`

`xml_id`, `name` (required); `lines[]` with `product_xmlid`, optional `qty`
(default 1.0) and `description`; optional `note` (terms and conditions),
`number_of_days` (validity), `sequence`. Creates `sale.order.template`
("Angebotsvorlagen", see verified-patterns 4.20). Needs the `sales` bundle.
The products must be `sale_ok` and belong to the demo company.

## `projects[]`, `project_task_stages[]`, `project_tasks[]`

`projects`: `xml_id`, `name` (required); optional `partner_xmlid` (customer),
`stage_xmlid` (a `project.project.stage`, e.g.
`project.project_project_stage_1`), `description`, `date_start`, `date_end`,
`privacy_visibility` (`followers` | `invited_users` | `employees` | `portal`).
(Field Service via `project.is_fsm` was removed in Odoo 20 - `industry_fsm` no
longer exists; see verified-patterns 4.26.)

`project_task_stages`: `xml_id`, `name` (required); optional `sequence`
(default 10), `fold`. Task stages must be declared together with at least one
project (otherwise they would become personal stages of the installer).

`project_tasks`: `xml_id`, `name`, `project_xmlid` (required); optional
`stage_xmlid` (must be a defined task stage - the builder links every stage to
every project), `partner_xmlid`, `description`, `priority`
(`0`..`3`), `date_deadline`, `allocated_hours`.

Own bundle `project` (app `project`, requires `contacts`); creates the data
files `project_task_stage_data.xml`, `project_project_data.xml`,
`project_task_data.xml` in that order. See verified-patterns 4.21.

## `maintenance_equipment_categories[]`, `maintenance_equipment[]`,
`maintenance_requests[]` (bundle `maintenance`, Community)

`maintenance_equipment_categories`: `xml_id`, `name` (required); optional `note`.

`maintenance_equipment`: `xml_id`, `name` (required); optional `category_xmlid`,
`partner_xmlid` (vendor), `serial_no` (unique), `model`, `assign_date`,
`warranty_date`, `cost`, `note`.

`maintenance_requests`: `xml_id`, `name` (required); optional `equipment_xmlid`,
`maintenance_type` (`corrective` | `preventive`, default `corrective`),
`stage_xmlid` (default `maintenance.stage_0`), `priority` (`0`..`3`),
`description`, `schedule_date`, `close_date`.

The generator creates one `maintenance.team` per demo company
(`data/maintenance_team_data.xml`, always when the bundle is used) because a
request's team is required. See verified-patterns 4.22.

## `quality_points[]`, `quality_checks[]`, `quality_alerts[]` (bundle `quality`,
Enterprise, requires `mrp`)

`quality_points`: `xml_id`, `name` (required); optional `title`,
`product_xmlids` (list of local product xmlids; empty = all), `test_type`
(`passfail` | `measure`, default `passfail`), `measure_on` (`product` |
`operation`, default `product`), `note`. The generator sets the warehouse
manufacturing operation type as `picking_type_ids` and the shipped global team
`quality.quality_alert_team0`.

`quality_checks`: `xml_id`, `point_xmlid` (required), optional
`production_xmlid` (a `manufacturing_orders` xmlid), `product_xmlid` (must be
the production's finished product), `quality_state` (`none` | `pass` | `fail`,
default `none`), `note`.

`quality_alerts`: `xml_id`, `name` (required); optional `product_xmlid`,
`partner_xmlid`, `production_xmlid`, `stage_xmlid` (default
`quality.quality_alert_stage_0`), `priority` (`0`..`3`), `description`.

See verified-patterns 4.23/4.24.

## `subscriptions[]` (bundle `subscriptions`, Enterprise)

`xml_id`, `partner_xmlid`, `lines[]` (required); `plan` (`month` | `year`,
default `month`), `state` (default `draft`; only draft/sent), optional
`start_date`. Line: `product_xmlid`, `qty` (default 1.0), `description`.
Products should set `recurring_invoice: true` so the lines become recurring.
See verified-patterns 4.25.

## Recommended data volume ("rich demo" tier)

The generator emits exactly the records in the spec; there is no built-in
volume. For a convincing demo, aim for at least these counts per object type
(the engine warns below them, but never blocks the build). Only sections that
are already used are checked, so a deliberately omitted section never warns.
Source of truth: `engine/volume.py` (`RECOMMENDED_VOLUME`).

| Section | Minimum |
|---|---|
| `partners` | 30 |
| `products` | 25 |
| `invoices` | 10 |
| `crm_leads` | 15 |
| `purchase_orders` | 10 |
| `example_orders` (incl. `quotation`) | 12 |
| `helpdesk_tickets` | 12 |
| `quotation_templates` | 4 |
| `projects` | 3 |
| `project_tasks` | 12 |
| `manufacturing_orders` | 8 |
| `stock_quants` | 10 |
| `subscriptions` | 6 |
| `maintenance_equipment` | 6 |
| `maintenance_requests` | 8 |
| `quality_points` | 4 |
| `quality_checks` | 6 |
| `quality_alerts` | 4 |

Spread invoices/orders across several months and mix customer and vendor
documents; vary partner countries, individual contacts (`is_company: false`)
and pipeline stages so the demo looks realistic rather than uniform.

## Compact tables (token-saving, optional)

Every list-of-records section (`partners`, `products`, `invoices`, `example_orders`,
`boms`, …) and every nested `lines` list may be written as a **table** instead of
a list of objects: the first element is a header row of field names, the rest are
value rows of equal length. The repeated keys disappear, the parsed result is
identical. Values keep their JSON type. Both forms can be mixed freely, also
between sections.

```jsonc
"partners": [
  ["xml_id", "name", "country_xmlid", "street", "city", "zip", "vat"],
  ["p_c1", "Autohaus Vogel GmbH", "base.de", "Karlstrasse 100", "Karlsruhe", "76133", "DE305918243"],
  ["p_c2", "Brauerei Durlacher GmbH", "base.de", "Allee 12", "Karlsruhe", "76131", "DE128450379"]
],
"example_orders": [
  {"xml_id": "so1", "partner_xmlid": "p_c1", "state": "sent",
   "lines": [["product_xmlid", "qty", "description"],
             ["product_fin_shirt", 120.0, "T-Shirt bedruckt"]]}
]
```

The header names are validated against the record's dataclass (unknown column ->
error); a row with a different number of values than the header -> error. Only
fields present in the header are set - omitted optional fields use their defaults.
Use it for the bulky, repetitive sections; keep the verbose form where it reads
better.

## `customer_profile` (optional)

Free-form metadata about the customer's business, captured once so it can be
re-read cheaply and used to keep the demo data customer-specific. It generates
**no** Odoo records.

| Field | Note |
|---|---|
| `industry` | e.g. "Werbemittelhandel" |
| `business_model` | e.g. "B2B Full-Service von Beschaffung bis Logistik" |
| `product_domains` | list of domain terms; drives the relatability check |
| `customer_segments` | list, e.g. ["Mittelstand", "Handwerk"] |
| `region` | e.g. "Karlsruhe" |

`product_domains` feeds `check_spec_relatability` (`engine/validate.py`): a
`generate` run warns when the profile names domains but **no** product
name/description matches any term (the catalog looks generic/copied). A leftover
scaffold placeholder (`TODO`) anywhere in the spec is an **error** that stops the
build.

## What static validation rejects

`engine/validate.py` + `engine/model.py` enforce among other things: unknown
`product.type`, unsafe `sale.order` states, unsafe `purchase.order` state,
`account.move` with `state`, `project.task` with `state`, `stock.quant` with
`inventory_quantity`, `standard_price` without company context, duplicate
barcodes, a `project.task` whose stage is not linked via `project.type_ids`,
`project.task` without `project.project`, dangling `xml_id` references, missing
manifest files, `quality_points` without `mrp`, invalid maintenance/quality/
subscription enum values, `recurring_invoice` without a `sale_subscription`
dependency, and a recurring product on a non-draft `sale.order`/quotation.

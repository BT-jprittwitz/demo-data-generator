# Verified Odoo 19.0 patterns for demo data

Each block is verified against the real 19.0 source. The numbering
(4.1, 4.2, ...) is stable and is referenced by code comments and
`engine/validate.py`.

Paths relative to the Odoo checkout:

- Community: `odoo/addons/<module>/...`
- Enterprise: `enterprise/<module>/...`
- core/base: `odoo/odoo/addons/base/...`, ORM: `odoo/orm/...`

Local reference checkout: `../odoodemo-local/repos/odoo/addons/` or
`../odoodemo-local/repos/enterprise/`. Alternatively GitHub `github.com/odoo/odoo`
branch `19.0`.

**Basic rule:** `_load_records_create()` (`odoo/tools/convert.py`, `odoo/orm/models.py`)
calls the **real ORM `create()`** including all overrides when loading real demo
XML. Every status/state field that is set can trigger real business logic.

---

## 4.1 `product.product` — only ONE record per product

`product.product` inherits from `product.template` via
`_inherits = {'product.template': 'product_tmpl_id'}`. A single `product.product`
record with the template fields set directly creates the template automatically as
well.

**Landmine:** A separate `product.template` AND `product.product` (with
`product_tmpl_id=ref(template)`) creates two variants of the same attribute-less
combination -> `psycopg2.errors.UniqueViolation: duplicate key value violates
unique constraint "product_product_combination_unique"`.

```xml
<record id="product_fin_conveyor" model="product.product">
    <field name="name">Foerderbandanlage FB-2000</field>
    <field name="type">consu</field>
    <field name="is_storable">True</field>
    <field name="sale_ok">True</field>
    <field name="purchase_ok">False</field>
    <field name="list_price">18500.00</field>
    <field name="company_id" ref="demo_company" />
</record>
```

Allowed `type` values in this generator: `consu`, `service`.

## 4.2 Derive `mrp.bom.product_tmpl_id` from a `product.product` xmlid

`mrp.bom.product_tmpl_id` needs a `product.template` ID. The `model` attribute
on `<field>` binds `obj()` to that model, then normal field navigation:
```xml
<field name="product_tmpl_id" model="product.product"
       eval="obj(ref('product_fin_conveyor')).product_tmpl_id.id" />
```

## 4.3 `sale.order.state` — `state='sale'` is unsafe

States: `draft` (quotation), `sent`, `sale` (order), `cancel`.

**Landmine:** `state='sale'` in demo XML triggers for `consu` lines
`sale_stock._action_launch_stock_rule()` -> `UserError: No rule has been found
to replenish "..." in "Customers"`, because a fresh company has no warehouse.

**Safe:** `draft` or `sent`. `model.SaleOrder` rejects other values,
and so does `validate.py`.

## 4.4 `res.company.create()` — automatic partner creation

`res.company.create()` automatically creates a `res.partner` and takes over
`name`, `vat`, `email`, `phone`, `website`, `country_id`. `street`/`city`/`zip`
are compute+inverse on the company and are written through — this works.

## 4.5 `res.company` — visibility for the UI login admin (`post_init_hook`)

**Landmine (real):** `res.company.create()` only adds the new company to
`company_ids` for `self.env.user` and `SUPERUSER_ID`, **not** for the normal
UI login admin (`base.user_admin`, uid 2). Without a fix, all company-keyed
demo data is invisible to the UI admin.

**Fix:** `post_init_hook(env)` that adds `base.user_admin` to `company_ids` and
sets it as the active company (see `engine/manifest.py`).
Signature in 19.0: `def post_init_hook(env):` (`odoo/modules/loading.py`).
Import: `from odoo.fields import Command` (not `from odoo import Command`).

## 4.6 Dead end: server actions for file access

Odoo server actions (`safe_eval`) forbid `with` statements and block `open()`.
For deployment files/logs use the container/CI console, not Odoo server actions.

## 4.7 `standard_price` is `company_dependent` — needs company context

`product.product.standard_price` is `company_dependent=True`. Company-dependent
fields are stored by `convert_to_column_insert()` under the key
**`record.env.company.id`** (`odoo/orm/fields.py`) — that is the *active company
of the loading env*, not the record's `company_id` field.

**Landmine:** Without context the value ends up against the wrong company and
seems to "disappear" in the demo company. The historical `bt_demo_mfg.zip` had
exactly this bug.

**Fix:** wrap the `<record>` with context as soon as `standard_price` is set:
```xml
<record id="product_comp_steel" model="product.product"
        context="{'allowed_company_ids': [ref('demo_company')]}">
    <field name="standard_price">38.5</field>
    ...
</record>
```
`env.company` reads `allowed_company_ids` without a sudo check; the loading env is
sudo. `records.py` does this automatically; `validate.py` fails without context.
`list_price` (on `product.template`) is **not** company_dependent.

## 4.8 `--test-enable` NOT for the installation smoke test

`--test-enable` runs the test suites of **all** installed modules (998
base tests etc., ~3.5 min, many irrelevant `ERROR` lines from
`base.tests.test_cli`) and looks like a hang. Omit it for the smoke test.
Details: `install-test-protocol.md`.

## 4.9 `crm.lead` — leads and opportunities are the same model

`crm/models/crm_lead.py`: no model `crm.opportunity`; field `type`
`{'lead','opportunity'}` (`:123-125`). Only `name` (`:102`) and `type`
(`:124`) are required. `stage_id`/`team_id`/`company_id`/`probability` are
compute+store+readonly=False. Default stages `crm.stage_lead1`..`lead4` exist
(`crm/data/crm_stage_data.xml`). `stage_lead4` is `is_won=True` -> a constraint
enforces `probability=100` (`:262-266`); the generator only uses `lead1`..`lead3`.
Create your own `crm.team` per demo company (`company_id` optional,
`sales_team/models/crm_team.py:88`).

## 4.10 `purchase.order` + `purchase_stock` — `picking_type_id` is NOT NULL (real)

`purchase.order.state`: `draft/sent/to approve/purchase/cancel`
(`purchase/models/purchase_order.py:105-111`); `create()` only creates the
sequence name. **But** `purchase_stock` (auto_install with `purchase`+`stock`)
adds `picking_type_id = fields.Many2one('stock.picking.type', required=True,
default=_default_picking_type, ...)` (`purchase_stock/models/purchase_order.py:24`).
Its default reads `self.env.company` — during XML loading the *main* company, and
a company created via XML has no warehouse -> NULL ->
`psycopg2.errors.NotNullViolation: null value in column "picking_type_id"`.

**Fix (both):** (1) Create a `stock.warehouse` for the demo company **before**
the POs. (2) Set `picking_type_id` explicitly:
```xml
<field name="picking_type_id" model="stock.warehouse"
       eval="obj(ref('warehouse_demo')).in_type_id.id"/>
```
`state` stays `draft`/`sent` (state `purchase` creates pickings,
`purchase_stock/models/purchase_order_line.py:94-99`). Field names 19.0:
`product_uom_id` (not `product_uom`), `tax_ids` (not `taxes_id`),
`purchase.order.line.date_planned`.

## 4.11 Chart of accounts for a new company (`account.chart.template`)

`res.company.create()` only loads a chart of accounts if the new company has a
`parent` with `chart_template` — and it does so deferred in `precommit`
(`account/models/company.py:487-501`). A company created via XML without
`parent_id` does **not** get a chart of accounts automatically.

**Fix:** synchronous `<function>` call directly after the company is created
(pattern from `account/demo/account_demo.xml:35-40`):
```xml
<function model="account.chart.template" name="try_loading">
    <value eval="[]"/>
    <value>ch</value>
    <value model="res.company" eval="obj().env.ref('bt_demo_nishcom.demo_company')"/>
    <value name="install_demo" eval="False"/>
</function>
```
`try_loading(template_code, company, install_demo=False, force_create=True)`
(`account/models/chart_template.py:140`). `_load` requires the system user
(`:183-184`). Template codes: e.g. `ch` (l10n_ch), `generic_coa`.
**Important:** declare the localization (e.g. `l10n_ch`) as a module dependency,
otherwise `_load` installs it in the middle of loading and resets the
transaction/registry (`chart_template.py:191-195`). Accounts/journals have
company-dependent xmlids `account.<company_id>_...` (`:683-697`) — do not
hardcode them, leave it to the ORM default.

## 4.12 `account.move` — `state='posted'` is forbidden in `create()`

`account/models/account_move.py`: `create()` raises
`UserError('You cannot create a move already in the posted state. ...')` (`:3895-3896`).

**Pattern:** create as `draft` (`move_type`, `partner_id`, `invoice_date`,
`invoice_line_ids` with `product_id`/`quantity`/`price_unit`/`name`, `company_id`,
with company context), then post via `action_post()`. The ORM computes
`journal_id`/`account_id`/`currency_id`. Posting happens in the `post_init_hook`
(Odoo's own pattern `account/demo/account_demo.py:70-98`), errors are swallowed
per move. `move_type`: `out_invoice` (customer), `in_invoice` (vendor).

## 4.13 `stock.quant` (stock) + `stock.warehouse` (warehouse)

A new company created via XML gets **no warehouse**:
`res.company.create()` only creates locations (`stock/models/res_company.py:163-172`),
`_create_per_company_picking_types()` is an empty stub (`:174-175`),
`create_missing_warehouse()` only kicks in if no warehouse exists globally
(`:114-126`). Creating a `stock.warehouse` with only `company_id` is enough
(`stock/data/stock_demo.xml:178-180`).

**Stock without a stock move:** set `stock.quant` with `quantity`, **not**
`inventory_quantity`/`inventory_quantity_auto_apply`. Only then does the
create override take the inventory branch and call `_apply_inventory()` ->
`stock.move` + valuation (`stock/models/stock_quant.py:267-310`, `:996-1035`).
Without these fields `super().create()` runs; `quantity` is writable via ORM/XML
(UI readonly). `location_id` = `obj(ref('warehouse_demo')).lot_stock_id.id`.

## 4.14 `helpdesk.ticket` (Enterprise) — a ticket needs its own company's team

`helpdesk.ticket` is standalone (no `project.task` inherit,
`helpdesk/models/helpdesk_ticket.py:25`). In practice only `name` is required (`:76`).
`company_id` is `related='team_id.company_id'` (`:84`); a constraint requires
that `partner_id.company_id` matches (`_check_partner_id_has_the_same_company`,
`:1071-1075`). The default team `helpdesk.helpdesk_team1` belongs to the
main company. `res.company.create()` does automatically create a team per company
(`enterprise/helpdesk/models/res_company.py:10-14`), but without an xmlid — the
generator therefore creates its **own** `helpdesk.team` with the demo company.
Stages `helpdesk.stage_new`/`stage_in_progress`/`stage_solved` exist globally
(`helpdesk/data/helpdesk_data.xml`).

## 4.15 Accounting vs. invoicing: `account` alone is only "Invoicing"

The Community module `account` yields "Invoicing" in the UI. Full accounting is
`account_accountant` (Enterprise, `depends: ['account','mail_enterprise','web_tour']`,
`auto_install: True`), which installs `account_reports` as well. Auto-install only
applies together with `mail_enterprise`; in a fresh Community DB it remains
"Invoicing". Spec option `accounting_app`: `"full"` (default, Enterprise) vs.
`"invoicing"` (only `account`, Community-compatible).

## 4.16 Demo-data language: `lang` context + country mapping

Translatable fields (`translate=True`, e.g. `product.template.name`,
`description_sale`, `res.company.name`) are stored on insert by
`convert_to_column_insert()` as `PsycopgJson({'en_US': value, record.env.lang or
'en_US': value})` (`odoo/orm/fields_textual.py:92-98`). So the value is **always**
stored under `en_US` AND under the current `env.lang`; reads fall back to `en_US`
via `get_translation_fallback_langs()` (`:229-237`). Consequence: setting
`context="{'lang': 'de_CH'}"` on a `<record>` stores the demo text in the target
language **without** losing the English fallback.

Language selection: the spec's optional `language` field overrides; otherwise it
is derived from the company country via `COUNTRY_DEFAULT_LANGUAGE` in
`engine/model.py` (primary language per country, e.g. `ch` -> `de_CH`, `de` ->
`de_DE`, `us`/`gb` -> `en_*`). All used codes exist in `res.lang`
(`base/data/res.lang.csv`).

The `post_init_hook` activates the language (`res.lang.active = True`, cf.
`res_lang.py:_activate_lang`) and sets `company.partner_id.lang`.

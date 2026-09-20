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

## 4.17 `mrp.production` — a draft manufacturing order needs a warehouse

Source: `odoo/odoo@19.0`, `addons/mrp/models/mrp_production.py`.

- Required for `create()`: `product_id` (`check_company`), `product_qty` (SQL
  Constraint `check (product_qty > 0)`), `product_uom_id`, `picking_type_id`,
  `location_src_id`, `location_dest_id`, `date_start` (default now). The engine
  sets `product_id`/`bom_id`/`product_qty`/`company_id`/`picking_type_id` and
  lets `product_uom_id` and the locations be computed from product/BOM/operation
  type.
- `state` is `compute='_compute_state', store=True, readonly=True` → **never set
  it**. A freshly created MO is `draft`; `create()` does not call
  `action_confirm` (only `button_confirm`/`action_confirm` do), so **no stock is
  posted**. It does generate draft `stock.move`/`mrp.workorder` records and a
  `mrp.production.group` (`create()`).
- `picking_type_id` (`domain code='mrp_operation'`, required, `check_company`):
  `_compute_picking_type_id`/`_get_default_picking_type_id` search the company's
  warehouse manufacturing operation type (`stock.warehouse.manu_type_id`, added
  by mrp). Without a company warehouse the compute warns
  (`_warehouse_redirect_warning`). Set it explicitly:
  `eval="obj(ref('warehouse_demo')).manu_type_id.id"` (same `obj()` pattern as
  4.10).
- Because of this, the warehouse data file MUST load **before** the
  manufacturing orders, and `needs_warehouse` includes mrp (`engine/model.py`;
  `engine/manifest.py`). The dependency is one-sided: a warehouse never implies
  manufacturing. This is the concrete case behind the general rule "producing
  without a warehouse does not work".

## 4.18 Auto-created demo user (name = company, admin rights)

Goal: after the demo appointment the customer can log in without a manual user
setup step. The `post_init_hook` therefore creates a `res.users` with
`name` = company name and the same rights as `base.user_admin`.

Verified against `odoo/odoo@19.0`, `odoo/addons/base/models/res_users.py`:

- **`_inherits = {'res.partner': 'partner_id'}`** (`:165`): setting `name` in
  `create()` creates the related partner automatically (`odoo/orm/models.py`
  `create()` -> parent creation, `:4698-4714`). Do NOT pass `partner_id`.
- **`res.users.create()`** (`:578-594`) syncs `partner_id.company_id =
  company_id` when the partner has a company. `res.partner.write()` rejects
  `company_id` if it conflicts with the user's company (`res_partner.py:901-909`)
  — keeping both at the demo company avoids that.
- **Required:** `login` (`:216`), `company_id` (`:245`, default
  `env.company`). `password` (`:217`) is compute+inverse; plain text is hashed
  by `_set_password()` (`:294`). Default `group_ids` is
  `_default_groups()` = `base.group_user` (`:203-212`), NOT admin — the groups
  must be set explicitly.
- **UNIQUE(login)** (`_login_key`, `:274-275`): if a user with the login already
  exists (e.g. a second demo package in the same DB) `create()` raises. The
  hook searches first, skips creation and only adds the new demo company to the
  existing user's `company_ids` (so both packages stay visible) instead of
  aborting the install.
- **Groups:** `base.group_system` implies only `group_erp_manager` +
  `group_sanitize_override` (`base/security/base_groups.xml:35-40`). The app
  manager groups (`sales_team.group_sale_manager`,
  `account.group_account_manager`, `stock.group_stock_manager`,
  `purchase.group_purchase_manager`, `helpdesk.group_helpdesk_manager`, ...)
  are linked to `base.user_admin` by the modules, NOT implied by
  `group_system`. Copy `admin.group_ids` to get the same rights.
- **`company_ids`** is a `res_company_users_rel` m2m (`:247-248`); a constraint
  requires `company_id in company_ids` (`_check_user_company`, `:501-510`). Add
  the demo company (`admin.company_ids | company`) so the user can switch.
- **`no_reset_password` context** (`odoo/addons/auth_signup/models/res_users.py:269-280`):
  without it, `create()` sends a sign-up invitation when the partner has an
  email. Pass the context (Odoo's own pattern, e.g.
  `base/data/res_users_demo.xml:85`).
- **`password` policy:** with `auth_password_policy` installed
  (`_set_password` -> `_check_password_policy`), the password must respect
  `auth_password_policy.minlength`. The default login/password `demo`/`demo`
  is short; if a customer sets a long minimum, the spec value must comply.

Login/password default: `demo`/`demo` (`engine/manifest.py` `DEMO_USER_LOGIN`/
`DEMO_USER_PASSWORD`).

## 4.19 Partner `vat` is checksum-validated once `base_vat` is installed (real)

Source: `odoo/odoo@19.0`, `addons/base_vat/models/res_partner.py` +
`addons/account/models/partner.py`.

- `res.partner.vat` is `fields.Char(inverse="_inverse_vat", store=True)`
  (`base_vat/models/res_partner.py:104`); the inverse calls `_check_vat()`
  (`account/models/partner.py:849-854`) -> `_run_vat_checks(..., validation='error')`
  (`base_vat/models/res_partner.py:106-164`). An invalid number raises
  `ValidationError('The VAT number [..] does not seem to be valid..')` and aborts
  the XML load (`_load_records_create` calls the real ORM `create()`).
- Which checker runs comes from `_check_vat_number` (`:346-350`):
  `check_vat_<cc>` if defined, else `stdnum.util.get_cc_module(cc, 'vat')`.
  Germany overrides it (`:898-901`): `stdnum.de.vat.is_valid(vat) or
  stdnum.de.stnr.is_valid(vat)`. So `DE` numbers must satisfy the ISO 7064
  Mod 11,10 checksum (`stdnum/iso7064/mod_11_10.py`); a syntactically plausible
  but checksum-invalid number (e.g. `DE118273456`) fails.
- `base_vat` is only present when a localization pulls it in. `l10n_de`
  depends on `base_vat` (`l10n_de/__manifest__.py:19-25`), `l10n_ch` does
  **not** - which is why `bt_demo_nishcom`'s invented Swiss/German VAT numbers
  install fine but the same invented numbers abort a `de_skr03`/`de_skr04`
  package. The context key `no_vat_validation` switches the check off
  (`:146`), but that would only silence, not fix, the demo data.
- **Fix:** use checksum-valid VAT numbers. Compute the check digit, do not guess:
  - DE: `stdnum.iso7064.mod_11_10.calc_check_digit('11827345')` -> `4` ->
    `DE118273454`.
  - AT: `stdnum.at.uid.calc_check_digit('U2233445')` -> `4` -> `ATU22334454`.
  - CH (`CHE-142.028.625`) is unaffected here (no `base_vat`), but keep the
    number plausible with the correct `CHE-xxx.xxx.xxx` format.
- `engine/validate.py` implements the DE (Mod 11,10) and AT (Luhn) checksum and
  flags invalid partner VAT numbers as errors **only** when the manifest
  depends on `base_vat`/`l10n_de`; `engine/tests/test_engine.py
  (VatValidationTests)` pins both checks against the stdnum reference values.

## 4.20 Quotation templates `sale.order.template` ("Angebotsvorlagen")

Source: `odoo/odoo@19.0`,
`addons/sale_management/models/sale_order_template.py`,
`sale_order_template_line.py`. Module: `sale_management` (already a hard
dependency of every generated module, `engine/manifest.py`).

- `_name = 'sale.order.template'`; **only `name` is required**
  (`sale_order_template.py:18`). `company_id` is a plain m2o with default
  `env.company` (`:16`) - set it explicitly to the demo company so the template
  and its lines belong to it.
- `note` = "Terms and conditions" (`fields.Html(translate=True)`, `:19`);
  `number_of_days` = quotation validity (`:27`); `sequence` (`:20`).
- `sale_order_template_line_ids` is a One2many to `sale.order.template.line`
  (`:47-50`). The line has TWO SQL constraints
  (`sale_order_template_line.py:12-19`):
  - `_accountable_product_id_required`: `display_type IS NULL` requires
    `product_id IS NOT NULL AND product_uom_id IS NOT NULL`;
  - `_non_accountable_fields_null`: `display_type` set forbids
    product/quantity/UoM.
    So a product line MUST set both `product_id` and `product_uom_id`.
- `product_uom_id` is compute+store+`readonly=False`+`precompute=True`
  (`:45-50`, computed from `product_id.uom_id`). **Set it explicitly**
  (`uom.product_uom_unit`) so the DB CHECK can never race the compute.
  `product_uom_qty` is required (default 1, `:51-55`); `name` is the
  (translatable) description (`:39-42`).
- `_check_company_id` (`:86-124`) rejects products whose `company_id` is not
  accessible to the template company. Since products are created for the demo
  company, the template's `company_id` must be the demo company too.
- `create()` runs `_update_product_translations()` (`:134-138`) - harmless for
  our XML load (it only rewrites line names that match the product description).
- **Engine:** `QuotationTemplate`/`QuotationTemplateLine` in `engine/model.py`,
  renderer `records.quotation_template_record`, file
  `data/sale_order_template_data.xml`; section `quotation_templates` lives in
  the `sales` bundle. `require_signature`/`require_payment` are computed from
  the company (`:31-45`) and are therefore not set.

## 4.21 Projects `project.project` / `project.task` / task stages

Source: `odoo/odoo@19.0`, `addons/project/models/project_project.py`,
`project_task.py`, `project_task_type.py`, `project_project_stage.py`;
`addons/project/data/project_data.xml`, `data/project_demo.xml`. Module:
`project`.

- **`project.project`** (`project_project.py`): only `name` is required
  (`:91`). `company_id` is compute+store+`readonly=False` (`:95`,
  `_compute_company_id :245-252`); `partner_id` must belong to the project's
  company (`_inverse_company_id :260-279`). `privacy_visibility` is required,
  default `'portal'` (`:119-...`). No alias is created unless `alias_name` is
  set (`mail.alias.mixin.optional`). No analytic account is created
  automatically (`_create_analytic_account` is not called on `create`).
- **Project stages** (`project.project.stage`): the four core records
  `project.project_project_stage_0..3` ("To Do"/"In Progress"/"Done"/
  "Cancelled") ship as `noupdate="1"` data (`data/project_data.xml`) with
  `company_id = False`, so they are usable by the demo company. `stage_id` has
  default `_default_stage_id` (lowest sequence, `:68-70`) and is group-gated
  (`groups="project.group_project_stages"`, `:158-159`).
- **Task stages** (`project.task.type`): there are **NO default task stages** in
  19.0 - they must be created. `name` required (`project_task_type.py`).
  `project_ids` is the inverse of `project.project.type_ids` (same relation
  `project_task_type_rel`).
- **`project.task`** (`project_task.py`): only `name` required (`:152`).
  `project_id` (`:193`), `stage_id` (`:161-163`) and `company_id` (`:235`) are
  compute+store+`readonly=False`. `state` is compute+store+required with default
  `'01_in_progress'` (`:174`) - **never set it**.
- **Landmine - a task's stage must be linked to its project.**
  `_compute_stage_id` (`:688-695`) resets the stage when
  `project not in task.stage_id.project_ids`; `stage_find` (`:974-993`) only
  searches `project.task.type` where `project_ids = project.id`. Pattern
  (`data/project_demo.xml`): create the task stages without `project_ids`, then
  link them through `project.project.type_ids` with
  `Command.link(ref('stage'))`.
- **Landmine - task stages vs. personal stages.** `project.task.type.user_id` is
  compute+store with default `_default_user_id` = `env.uid` when no
  `default_project_id` context is set. `_compute_user_id` (`project_task_type.py`)
  clears `user_id` once `project_ids` is set, and
  `_check_personal_stage_not_linked_to_projects` forbids `user_id` + `project_ids`
  together. Creating the stage without `project_ids` (and linking from the
  project side) lets the compute clear `user_id` - the canonical demo pattern.
  Because of this, `engine/model.py` rejects `project_task_stages` without a
  project (they would become personal stages of the installer).
- **Engine:** `Project`/`ProjectTaskStage`/`ProjectTask` in `engine/model.py`,
  renderers `records.project_*_record`, files
  `data/project_task_stage_data.xml` -> `data/project_project_data.xml` ->
  `data/project_task_data.xml` (order matters: stages before projects before
  tasks), section/bundle `project` (app `project`, requires `contacts`).
  `engine/validate.py` flags a `project.task` whose `stage_id` is not linked via
  `project.type_ids`, and `project.task` without `project.project`.

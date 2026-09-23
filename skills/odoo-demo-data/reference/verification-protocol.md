# Verification protocol: new object type or new field

Goal: **Never guess Odoo field names or behavior.** Every new object type and
every new field is first verified against the real Odoo 20.0 source.

## Where the source lives

- Local checkout (development machine):
  - Community: `../odoodemo-local-20/repos/odoo/addons/<module>/`
  - Enterprise: `../odoodemo-local-20/repos/enterprise/<module>/`
  - base/ORM: `../odoodemo-local-20/repos/odoo/odoo/addons/base/`, `../odoodemo-local-20/repos/odoo/odoo/orm/`
- Alternatively GitHub `github.com/odoo/odoo`, branch/tag `20.0`.

## What to check (checklist)

For every new object type:

1. **`_name`** and if applicable `_inherits`/`_inherit` (delegation? mixins?).
2. **Required fields** for `create()` (`required=True`) as well as DB constraints
   (NOT NULL, SQL/`@api.constrains`).
3. **Field names exactly** (case, `_id` suffixes). Especially:
   `product_uom_id` vs. `product_uom`, `tax_ids` vs. `taxes_id`.
4. **`create()`/`write()` overrides** of the model and relevant bridge modules —
   what real logic do they trigger?
5. **Status/state fields**: Which values trigger real business logic
   (picking, procurement, posting, mail)? Only use verified-safe values.
6. **company_dependent fields**: need `context="{'allowed_company_ids': [...]}"`
   on the `<record>` (see verified-patterns 4.7).
7. **Company coupling**: Does a compute/domain filter by `env.company` or
   `company_id`? A new company may need upstream master data
   (e.g. `stock.warehouse`, `helpdesk.team`).
8. **Existing example `<record>` blocks** in the module's `demo`/`data` XML files or
   in `tests/` — they show the canonical way, including `<function>` tags.

## Procedure in code

1. Add findings to `reference/verified-patterns.md` (model, source
   `file:line`, minimal XML snippet, landmine).
2. Add dataclass + `__post_init__` validation in `engine/model.py`
   (limit allowed values, reject unclear values).
3. Loader in `engine/spec_loader.py`, renderer in `engine/records.py`.
4. If possible a mechanical rule in `engine/validate.py` (landmine
   -> error) and a test in `engine/tests/test_engine.py`.
5. Do not verify obvious values "proactively" — only what a concrete
   customer needs ("demand-driven growth").

## On installation error

**Always read/request the complete traceback** before attempting a fix.
A fix without a traceback is guessing. The traceback shows the concrete line
in the Odoo source that triggers the error.

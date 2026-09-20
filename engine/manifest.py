"""Renders __manifest__.py and hooks.py from the fixed, verified pattern
(verified-patterns.md 4.5). Only customer data is parameterised (technical_name,
title, summary, description, data file list) - the structure itself
(post_init_hook, Command import, depends skeleton) stays fixed.
"""
from __future__ import annotations

from .model import CustomerSpec

AUTHOR = "braintec"
WEBSITE = "https://www.braintec.com"
LICENSE = "LGPL-3"

# Login/password of the auto-created demo user (name = company, same groups as
# base.user_admin). Fixed by design: after a demo appointment the customer can
# log in immediately without a manual user setup step. If the login already
# exists in the target DB, creation is skipped instead of aborting the install
# (res.users has UNIQUE(login), verified-patterns.md 4.18).
DEMO_USER_LOGIN = "demo"
DEMO_USER_PASSWORD = "demo"

# Explicit localization module dependency per chart-of-accounts template code.
# The localization MUST be declared as a dependency: otherwise
# account.chart.template._load() installs it during data loading and resets the
# transaction/registry mid-load (verified-patterns.md 4.11). Only verified codes
# are listed (demand-driven growth); an unmapped code gets no dependency.
CHART_TEMPLATE_MODULE = {
    "ch": "l10n_ch",
    "de_skr03": "l10n_de",
    "de_skr04": "l10n_de",
}


def data_files(spec: CustomerSpec) -> list[str]:
    files = ["data/res_company_data.xml"]
    if spec.company.chart_template:
        files.append("data/account_chart_data.xml")
    if spec.crm_leads:
        files.append("data/crm_team_data.xml")
    if spec.helpdesk_tickets:
        files.append("data/helpdesk_team_data.xml")
    if spec.partners:
        files.append("data/res_partner_data.xml")
    # Task stages MUST exist before the projects that link them (type_ids).
    if spec.project_task_stages:
        files.append("data/project_task_stage_data.xml")
    if spec.projects:
        files.append("data/project_project_data.xml")
    if spec.project_tasks:
        files.append("data/project_task_data.xml")
    if spec.products:
        files.append("data/product_data.xml")
    if spec.boms:
        files.append("data/mrp_bom_data.xml")
    if spec.needs_warehouse:
        files.append("data/stock_warehouse_data.xml")
    if spec.crm_leads:
        files.append("data/crm_lead_data.xml")
    if spec.purchase_orders:
        files.append("data/purchase_order_data.xml")
    if spec.stock_quants:
        files.append("data/stock_quant_data.xml")
    if spec.manufacturing_orders:
        files.append("data/mrp_production_data.xml")
    if spec.invoices:
        files.append("data/account_move_data.xml")
    if spec.helpdesk_tickets:
        files.append("data/helpdesk_ticket_data.xml")
    if spec.quotation_templates:
        files.append("data/sale_order_template_data.xml")
    if spec.quotation:
        files.append("data/sale_order_quotation_data.xml")
    if spec.example_orders:
        files.append("data/sale_order_examples_data.xml")
    return files


def depends(spec: CustomerSpec) -> list[str]:
    deps = ["sale_management"]
    if spec.needs_mrp:
        deps.append("mrp")
    if spec.needs_crm:
        deps.append("crm")
    if spec.needs_purchase:
        deps.append("purchase")
    # Purchase needs stock (purchase_stock: picking_type_id), stock needs it for
    # quants, manufacturing needs it for the warehouse operation type - see
    # engine/model.py needs_warehouse (dependency is one-sided: warehouse never
    # implies manufacturing).
    if spec.needs_warehouse:
        deps.append("stock")
    if spec.needs_account:
        deps.append("account")
        # Full accounting instead of Invoicing only: account_accountant
        # (Enterprise) also installs account_reports. `account` alone is shown
        # as "Invoicing" in the UI (verified-patterns.md 4.15).
        if spec.accounting_app == "full":
            deps.append("account_accountant")
    # l10n_ch/l10n_de explicitly as a dependency so that
    # account.chart.template._load() does not have to install the module during
    # data loading (which would reset the transaction/registry mid-load, see
    # account/models/chart_template.py). See CHART_TEMPLATE_MODULE.
    localization = CHART_TEMPLATE_MODULE.get(spec.company.chart_template or "")
    if localization:
        deps.append(localization)
    if spec.needs_helpdesk:
        deps.append("helpdesk")
    if spec.needs_project:
        deps.append("project")
    return deps


def render_manifest(spec: CustomerSpec) -> str:
    data_list = ",\n".join(f'        "{f}"' for f in data_files(spec))
    deps_list = ", ".join(f'"{d}"' for d in depends(spec))
    return f'''# -*- coding: utf-8 -*-
{{
    "name": {spec.module.title!r},
    "version": "19.0.1.0.0",
    "category": {spec.module.category!r},
    "summary": {spec.module.summary!r},
    "description": {spec.module.description!r},
    "author": {AUTHOR!r},
    "website": {WEBSITE!r},
    "depends": [{deps_list}],
    "data": [
{data_list}
    ],
    "demo": [],
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
    "application": False,
    "license": {LICENSE!r},
}}
'''


def render_init_py() -> str:
    return "from .hooks import pre_init_hook, post_init_hook\n"


def render_hooks_py(spec: CustomerSpec) -> str:
    """post_init_hook with four tasks:

    1. (verified-patterns.md 4.5) res.company.create() only adds the new company
       to company_ids of self.env.user and SUPERUSER_ID, not of the normal
       UI login admin (base.user_admin). Without this part the demo data is
       invisible to the UI admin after installation.
    2. (verified-patterns.md 4.16) Activate the demo-data language and set it on
       the company contact, so the data is stored/readable in that language.
    3. (verified-patterns.md 4.18) Create a demo login (name = company) with the
       same groups/companies as base.user_admin, so a demo appointment does not
       need a manual user setup afterwards.
    4. (verified-patterns.md 4.12) Invoices are created as draft in XML
       (state 'posted' is forbidden in create()) and posted here via
       action_post() - the verified Odoo-native pattern
       (account/demo/account_demo.py _post_load_demo_data). Errors are swallowed
       so a single problematic invoice does not abort the whole installation.
    """
    module = spec.module.technical_name
    company_xmlid = spec.company.xml_id
    language = spec.resolved_language
    invoice_block = ""
    if spec.invoices:
        invoice_block = '''
    if company:
        moves = env["account.move"].search([
            ("company_id", "=", company.id),
            ("state", "=", "draft"),
            ("move_type", "in", ("out_invoice", "in_invoice")),
        ])
        for move in moves:
            try:
                move.action_post()
            except Exception:
                # Do not abort the demo installation for a single invoice.
                pass
'''
    demo_user_block = f'''

def _create_demo_user(env, company, admin):
    """Create a demo login (name = company, same rights as base.user_admin).

    Verified against odoo/odoo@19.0 (verified-patterns.md 4.18):
    - ``res.users`` has a UNIQUE(login) constraint. If a user with this login
      already exists (e.g. a second demo package in the same database) the
      creation is skipped instead of aborting the installation.
    - ``res.users`` delegates to ``res.partner`` via ``_inherits``; ``name``
      creates/updates the related partner (partner company is synced to
      ``company_id`` in ``res.users.create()``).
    - ``group_ids`` is copied from ``base.user_admin`` (not just
      ``base.group_system``) because the app manager groups are linked to the
      admin by the modules and are NOT implied by ``group_system``.
    - ``no_reset_password`` (auth_signup) suppresses the sign-up invitation.
    """
    existing = env["res.users"].with_context(active_test=False).search(
        [("login", "=", "{DEMO_USER_LOGIN}")], limit=1
    )
    if existing:
        # Another demo package already created this login. Grant it access to the
        # new demo company instead of aborting on the UNIQUE(login) constraint.
        if company not in existing.company_ids:
            existing.write({{"company_ids": [Command.link(company.id)]}})
        return
    groups = admin.group_ids if admin else env.ref("base.group_system")
    companies = (admin.company_ids if admin else env["res.company"].browse()) | company
    env["res.users"].with_context(no_reset_password=True).create({{
        "name": company.name,
        "login": "{DEMO_USER_LOGIN}",
        "password": "{DEMO_USER_PASSWORD}",
        "lang": "{language}",
        "company_id": company.id,
        "company_ids": [Command.set(companies.ids)],
        "group_ids": [Command.set(groups.ids)],
    }})
'''
    return f'''# -*- coding: utf-8 -*-
from odoo.fields import Command


def pre_init_hook(env):
    """Activate the demo-data language before any data is loaded.

    Verified: env.lang raises UserError for a non-active language
    (odoo/orm/environments.py:302) and translatable fields are stored under
    env.lang, so the language must be active before the data files that set a
    lang context are loaded (verified-patterns.md 4.16).
    """
    lang_code = "{language}"
    if lang_code and lang_code != "en_US":
        lang = env["res.lang"].with_context(active_test=False).search(
            [("code", "=", lang_code)], limit=1
        )
        if lang and not lang.active:
            lang.active = True


def post_init_hook(env):
    """See docstring in engine/manifest.py (verified-patterns.md 4.5, 4.12, 4.16, 4.18)."""
    company = env.ref("{module}.{company_xmlid}", raise_if_not_found=False)
    admin = env.ref("base.user_admin", raise_if_not_found=False)
    if company and admin:
        admin.write({{
            "company_ids": [Command.link(company.id)],
            "company_id": company.id,
        }})
    if company:
        company.partner_id.lang = "{language}"
        _create_demo_user(env, company, admin)
{invoice_block}{demo_user_block}'''

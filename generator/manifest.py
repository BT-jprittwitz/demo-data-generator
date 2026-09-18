"""Rendert __manifest__.py und hooks.py aus dem festen, verifizierten Muster
in HANDOVER.md Abschnitt 4.5 / 5. Parametrisiert wird nur mit Kundendaten
(technical_name, title, summary, description, data-Dateiliste) - die Struktur
selbst (post_init_hook, Command-Import, depends-Grundgeruest) bleibt fest."""
from __future__ import annotations

from .model import CustomerSpec

AUTHOR = "braintec"
WEBSITE = "https://www.braintec.com"
LICENSE = "LGPL-3"


def data_files(spec: CustomerSpec) -> list[str]:
    files = ["data/res_company_data.xml"]
    if spec.partners:
        files.append("data/res_partner_data.xml")
    if spec.products:
        files.append("data/product_data.xml")
    if spec.boms:
        files.append("data/mrp_bom_data.xml")
    if spec.quotation:
        files.append("data/sale_order_quotation_data.xml")
    if spec.example_orders:
        files.append("data/sale_order_examples_data.xml")
    return files


def depends(spec: CustomerSpec) -> list[str]:
    deps = ["sale_management"]
    if spec.needs_mrp:
        deps.append("mrp")
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
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
    "application": False,
    "license": {LICENSE!r},
}}
'''


def render_init_py() -> str:
    return "from .hooks import post_init_hook\n"


def render_hooks_py(spec: CustomerSpec) -> str:
    """Fix aus HANDOVER.md 4.5: res.company.create() traegt die neue Company nur bei
    self.env.user und SUPERUSER_ID in company_ids ein, nicht beim normalen
    UI-Login-Admin (base.user_admin). Ohne diesen Hook sind die Demo-Daten nach der
    Installation fuer den UI-Admin unsichtbar."""
    module = spec.module.technical_name
    company_xmlid = spec.company.xml_id
    return f'''# -*- coding: utf-8 -*-
from odoo.fields import Command


def post_init_hook(env):
    """Traegt den UI-Login-Admin (base.user_admin) explizit in company_ids der neu
    angelegten Demo-Company ein und setzt sie als seine aktive Company, damit alle
    Demo-Daten direkt nach der Installation ohne manuellen Zwischenschritt sichtbar
    sind (verifizierter Hintergrund: HANDOVER.md Abschnitt 4.5)."""
    company = env.ref("{module}.{company_xmlid}", raise_if_not_found=False)
    admin = env.ref("base.user_admin", raise_if_not_found=False)
    if not company or not admin:
        return
    admin.write({{
        "company_ids": [Command.link(company.id)],
        "company_id": company.id,
    }})
'''

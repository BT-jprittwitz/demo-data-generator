"""Baut aus den Dataclasses in model.py die XML-Record-Elemente,
exakt nach den in HANDOVER.md Abschnitt 4 verifizierten Mustern.

Jede Funktion hier entspricht einem verifizierten Muster aus dem Handover-
Dokument. Wird ein neues Feld/Verhalten gebraucht, das hier noch nicht
vorkommt: NICHT einfach ergaenzen, sondern zuerst gegen den Odoo-19.0-Source
verifizieren und die Erkenntnis in HANDOVER.md nachtragen (harte Arbeitsregel,
Abschnitt 3).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from .model import Bom, Company, CustomerSpec, Partner, Product, SaleOrder
from .xmlgen import field_el, record_el, render_odoo_file


def company_record(c: Company) -> ET.Element:
    fields = [
        field_el("name", text=c.name),
        field_el("street", text=c.street),
        field_el("city", text=c.city),
        field_el("zip", text=c.zip),
        field_el("country_id", ref=c.country_xmlid),
    ]
    if c.vat:
        fields.append(field_el("vat", text=c.vat))
    if c.currency_xmlid:
        fields.append(field_el("currency_id", ref=c.currency_xmlid))
    return record_el("res.company", c.xml_id, fields)


def partner_record(p: Partner, company_xmlid: str) -> ET.Element:
    fields = [
        field_el("name", text=p.name),
        field_el("is_company", text=p.is_company),
        field_el("country_id", ref=p.country_xmlid),
    ]
    if p.vat:
        fields.append(field_el("vat", text=p.vat))
    fields += [
        field_el("street", text=p.street),
        field_el("city", text=p.city),
        field_el("zip", text=p.zip),
        field_el("supplier_rank", text=p.supplier_rank),
        field_el("customer_rank", text=p.customer_rank),
        field_el("company_id", ref=company_xmlid),
    ]
    return record_el("res.partner", p.xml_id, fields)


def product_record(p: Product, company_xmlid: str) -> ET.Element:
    """product.product traegt per _inherits automatisch das product.template mit an
    (HANDOVER.md 4.1) - hier NIE ein separates product.template-Record anlegen.

    standard_price ist company_dependent=True (verifiziert gegen
    odoo/orm/fields.py: convert_to_column_insert() schreibt den Wert unter dem Key
    record.env.company.id). Ohne expliziten context="{'allowed_company_ids': [...]}"
    auf dem <record> wuerde der Wert beim Laden gegen die falsche Company (die der
    Installationsumgebung, nicht die neue Demo-Company) gespeichert und waere in der
    Demo-Company unsichtbar (HANDOVER.md 4.7).
    """
    fields = [
        field_el("name", text=p.name),
        field_el("type", text=p.type),
        field_el("is_storable", text=p.is_storable),
        field_el("sale_ok", text=p.sale_ok),
        field_el("purchase_ok", text=p.purchase_ok),
        field_el("list_price", text=p.list_price),
    ]
    context = None
    if p.standard_price is not None:
        fields.append(field_el("standard_price", text=p.standard_price))
        context = f"{{'allowed_company_ids': [ref('{company_xmlid}')]}}"
    if p.default_code:
        fields.append(field_el("default_code", text=p.default_code))
    if p.barcode:
        fields.append(field_el("barcode", text=p.barcode))
    if p.weight is not None:
        fields.append(field_el("weight", text=p.weight))
    if p.volume is not None:
        fields.append(field_el("volume", text=p.volume))
    if p.description_sale:
        fields.append(field_el("description_sale", text=p.description_sale))
    fields.append(field_el("company_id", ref=company_xmlid))
    return record_el("product.product", p.xml_id, fields, context=context)


def bom_record(b: Bom, company_xmlid: str) -> ET.Element:
    """mrp.bom.product_tmpl_id braucht eine product.template-ID. Da nur eine
    product.product-xmlid existiert (HANDOVER.md 4.1), wird sie ueber
    obj(ref(...)).product_tmpl_id.id aufgeloest (HANDOVER.md 4.2)."""
    line_dicts = ", ".join(
        "(0, 0, {"
        f"'product_id': ref('{line.product_xmlid}'), "
        f"'product_qty': {line.qty}, "
        f"'product_uom_id': ref('{line.uom_xmlid}')"
        "})"
        for line in b.lines
    )
    fields = [
        field_el(
            "product_tmpl_id",
            model="product.product",
            eval_=f"obj(ref('{b.product_xmlid}')).product_tmpl_id.id",
        ),
        field_el("product_qty", text=b.qty),
        field_el("product_uom_id", ref=b.uom_xmlid),
        field_el("type", text="normal"),
        field_el("bom_line_ids", eval_=f"[{line_dicts}]"),
        field_el("company_id", ref=company_xmlid),
    ]
    return record_el("mrp.bom", b.xml_id, fields)


def sale_order_record(o: SaleOrder, company_xmlid: str) -> ET.Element:
    """state auf 'draft' oder 'sent' beschraenkt - model.SaleOrder.__post_init__
    verweigert jeden anderen Wert (HANDOVER.md 4.3: state='sale' triggert
    sale_stock-Beschaffungslogik, die ohne konfiguriertes Warehouse fehlschlaegt)."""
    line_dicts = ", ".join(
        "(0, 0, {"
        f"'product_id': ref('{line.product_xmlid}'), "
        f"'product_uom_qty': {line.qty}, "
        f"'name': {line.description!r}"
        "})"
        for line in o.lines
    )
    fields = [
        field_el("partner_id", ref=o.partner_xmlid),
        field_el("company_id", ref=company_xmlid),
    ]
    if o.date_order:
        fields.append(field_el("date_order", text=o.date_order))
    fields.append(field_el("state", text=o.state))
    fields.append(field_el("order_line", eval_=f"[{line_dicts}]"))
    return record_el("sale.order", o.xml_id, fields)


def render_res_company_xml(spec: CustomerSpec) -> str:
    return render_odoo_file([company_record(spec.company)])


def render_res_partner_xml(spec: CustomerSpec) -> str:
    return render_odoo_file([partner_record(p, spec.company.xml_id) for p in spec.partners])


def render_product_xml(spec: CustomerSpec) -> str:
    return render_odoo_file([product_record(p, spec.company.xml_id) for p in spec.products])


def render_mrp_bom_xml(spec: CustomerSpec) -> str:
    return render_odoo_file([bom_record(b, spec.company.xml_id) for b in spec.boms])


def render_sale_order_quotation_xml(spec: CustomerSpec) -> str:
    assert spec.quotation is not None
    return render_odoo_file([sale_order_record(spec.quotation, spec.company.xml_id)])


def render_sale_order_examples_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [sale_order_record(o, spec.company.xml_id) for o in spec.example_orders],
        noupdate=True,
    )

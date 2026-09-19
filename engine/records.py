"""Builds the XML record elements from the dataclasses in model.py, exactly
following the patterns verified against the Odoo 19.0 source
(see skills/odoo-demo-data/reference/verified-patterns.md).

Each function here corresponds to a verified pattern. If a new field/behaviour
is needed that is not covered yet, do NOT simply add it: first verify it against
the Odoo 19.0 source and record the finding in verified-patterns.md.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from .model import (
    Bom,
    Company,
    CrmLead,
    CustomerSpec,
    HelpdeskTicket,
    Invoice,
    Partner,
    Product,
    PurchaseOrder,
    SaleOrder,
    StockQuant,
)
from .xmlgen import field_el, record_el, render_odoo_file

# Fixed xml_ids for the per-company auto-created teams and the warehouse. Unique
# within a module because a module creates exactly one demo company.
CRM_TEAM_XMLID = "crm_team_demo"
HELPDESK_TEAM_XMLID = "helpdesk_team_demo"
WAREHOUSE_XMLID = "warehouse_demo"


def _context(language: str, company_xmlid: str | None = None) -> str:
    """Record context.

    ``lang`` makes translatable fields store the demo text in the target
    language (verified: odoo/orm/fields_textual.py convert_to_column_insert()
    always stores the value under ``en_US`` AND ``record.env.lang``, so other
    languages fall back to ``en_US`` - verified-patterns.md 4.16).

    ``allowed_company_ids`` sets the active company of the load environment
    (needed for company_dependent fields and company-sensitive defaults - see
    verified-patterns.md 4.7).
    """
    parts = [f"'lang': {language!r}"]
    if company_xmlid:
        parts.append(f"'allowed_company_ids': [ref('{company_xmlid}')]")
    return "{" + ", ".join(parts) + "}"


def company_record(c: Company, language: str) -> ET.Element:
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
    return record_el("res.company", c.xml_id, fields, context=_context(language))


def partner_record(p: Partner, company_xmlid: str, language: str) -> ET.Element:
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
    return record_el("res.partner", p.xml_id, fields, context=_context(language))


def product_record(p: Product, company_xmlid: str, language: str) -> ET.Element:
    """``product.product`` carries its ``product.template`` automatically via
    ``_inherits`` (verified-patterns.md 4.1) - never create a separate
    ``product.template`` record here.

    ``standard_price`` is ``company_dependent=True``: without
    ``allowed_company_ids`` the value would be stored against the wrong company
    (verified-patterns.md 4.7). The company part of the context is only added
    when ``standard_price`` is set; ``lang`` is always added so translatable
    text is stored in the demo language.
    """
    fields = [
        field_el("name", text=p.name),
        field_el("type", text=p.type),
        field_el("is_storable", text=p.is_storable),
        field_el("sale_ok", text=p.sale_ok),
        field_el("purchase_ok", text=p.purchase_ok),
        field_el("list_price", text=p.list_price),
    ]
    company_for_dependent = None
    if p.standard_price is not None:
        fields.append(field_el("standard_price", text=p.standard_price))
        company_for_dependent = company_xmlid
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
    return record_el(
        "product.product",
        p.xml_id,
        fields,
        context=_context(language, company_for_dependent),
    )


def bom_record(b: Bom, company_xmlid: str, language: str) -> ET.Element:
    """``mrp.bom.product_tmpl_id`` needs a ``product.template`` id. Since only a
    ``product.product`` xmlid exists (verified-patterns.md 4.1), it is resolved
    via ``obj(ref(...)).product_tmpl_id.id`` (verified-patterns.md 4.2)."""
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
    return record_el("mrp.bom", b.xml_id, fields, context=_context(language))


def sale_order_record(o: SaleOrder, company_xmlid: str, language: str) -> ET.Element:
    """``state`` is limited to 'draft'/'sent' - ``model.SaleOrder.__post_init__``
    rejects any other value (verified-patterns.md 4.3: state='sale' triggers
    sale_stock replenishment logic that fails without a configured warehouse)."""
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
    return record_el("sale.order", o.xml_id, fields, context=_context(language))


# ---------------------------------------------------------------------------
# ERP building blocks (CRM, purchase, stock, accounting, helpdesk). Each object
# type was verified against the Odoo 19.0 source first (verified-patterns.md
# 4.9-4.15).
# ---------------------------------------------------------------------------


def account_chart_function(spec: CustomerSpec) -> ET.Element:
    """Loads the chart of accounts for the freshly created demo company.

    Verified pattern from account/demo/account_demo.xml (account 19.0):
    self=[], template_code, company, install_demo=False. A company created via
    XML does NOT get a chart of accounts automatically (account/models/company.py
    create() only loads it when the company has a parent with chart_template, and
    then deferred in the precommit) - hence this explicit, synchronous call before
    products/invoices are created (verified-patterns.md 4.11).
    """
    assert spec.company.chart_template is not None
    fn = ET.Element("function", {"model": "account.chart.template", "name": "try_loading"})
    ET.SubElement(fn, "value", {"eval": "[]"})
    template_value = ET.SubElement(fn, "value")
    template_value.text = spec.company.chart_template
    ET.SubElement(
        fn,
        "value",
        {
            "model": "res.company",
            "eval": f"obj().env.ref('{spec.module.technical_name}.{spec.company.xml_id}')",
        },
    )
    ET.SubElement(fn, "value", {"name": "install_demo", "eval": "False"})
    return fn


def crm_team_record(spec: CustomerSpec) -> ET.Element:
    fields = [
        field_el("name", text=spec.resolved_crm_team_name),
        field_el("company_id", ref=spec.company.xml_id),
    ]
    return record_el("crm.team", CRM_TEAM_XMLID, fields, context=_context(spec.resolved_language))


def crm_lead_record(lead: CrmLead, company_xmlid: str, team_xmlid: str, language: str) -> ET.Element:
    fields = [
        field_el("name", text=lead.name),
        field_el("type", text=lead.type),
        field_el("stage_id", ref=lead.stage_xmlid),
        field_el("team_id", ref=team_xmlid),
        field_el("company_id", ref=company_xmlid),
    ]
    if lead.partner_xmlid:
        fields.append(field_el("partner_id", ref=lead.partner_xmlid))
    if lead.contact_name:
        fields.append(field_el("contact_name", text=lead.contact_name))
    if lead.email_from:
        fields.append(field_el("email_from", text=lead.email_from))
    if lead.phone:
        fields.append(field_el("phone", text=lead.phone))
    if lead.expected_revenue is not None:
        fields.append(field_el("expected_revenue", text=lead.expected_revenue))
    if lead.probability is not None:
        fields.append(field_el("probability", text=lead.probability))
    if lead.priority is not None:
        fields.append(field_el("priority", text=lead.priority))
    if lead.description:
        fields.append(field_el("description", text=lead.description))
    return record_el("crm.lead", lead.xml_id, fields, context=_context(language))


def purchase_order_record(o: PurchaseOrder, company_xmlid: str, language: str) -> ET.Element:
    """``purchase.order``. No ``button_confirm`` (it would create real pickings
    via purchase_stock) - the state stays draft/sent (verified-patterns.md 4.10).
    """
    line_dicts = []
    for line in o.lines:
        parts = [
            f"'product_id': ref('{line.product_xmlid}')",
            f"'name': {line.description!r}",
            f"'price_unit': {line.price_unit}",
            f"'product_qty': {line.qty}",
            "'product_uom_id': ref('uom.product_uom_unit')",
        ]
        if line.date_planned:
            parts.append(f"'date_planned': {line.date_planned!r}")
        line_dicts.append("(0, 0, {" + ", ".join(parts) + "})")
    fields = [
        field_el("partner_id", ref=o.partner_xmlid),
        field_el("company_id", ref=company_xmlid),
        # picking_type_id is required with purchase_stock (NOT NULL column). Its
        # default _default_picking_type uses env.company and would be NULL while
        # the demo company has no warehouse yet - so set it explicitly from the
        # demo warehouse (verified-patterns.md 4.10).
        field_el(
            "picking_type_id",
            model="stock.warehouse",
            eval_=f"obj(ref('{WAREHOUSE_XMLID}')).in_type_id.id",
        ),
        field_el("state", text=o.state),
    ]
    if o.date_order:
        fields.append(field_el("date_order", text=o.date_order))
    if o.partner_ref:
        fields.append(field_el("partner_ref", text=o.partner_ref))
    fields.append(field_el("order_line", model="purchase.order.line", eval_=f"[{', '.join(line_dicts)}]"))
    return record_el("purchase.order", o.xml_id, fields, context=_context(language))


def stock_warehouse_record(spec: CustomerSpec) -> ET.Element:
    """``stock.warehouse`` for the demo company. A new company gets NO warehouse
    automatically (stock/models/res_company.py create() only creates locations;
    create_missing_warehouse only runs when no warehouse exists globally) -
    verified pattern from stock/data/stock_demo.xml (verified-patterns.md 4.13).
    """
    fields = [
        field_el("company_id", ref=spec.company.xml_id),
        field_el("code", text="DEMO"),
    ]
    return record_el("stock.warehouse", WAREHOUSE_XMLID, fields, context=_context(spec.resolved_language))


def stock_quant_record(q: StockQuant, warehouse_xmlid: str, language: str) -> ET.Element:
    """``stock.quant`` WITHOUT ``inventory_quantity``: create() then takes the
    else branch ``super().create()`` and creates NO stock.move / no valuation
    entry (verified stock/models/stock_quant.py create()). ``quantity`` is
    writable via ORM/XML (readonly only in the UI). (verified-patterns.md 4.13)
    """
    fields = [
        field_el("product_id", ref=q.product_xmlid),
        field_el(
            "location_id",
            model="stock.warehouse",
            eval_=f"obj(ref('{warehouse_xmlid}')).lot_stock_id.id",
        ),
        field_el("quantity", text=q.qty),
    ]
    return record_el("stock.quant", f"quant_{q.product_xmlid}", fields, context=_context(language))


def account_move_record(inv: Invoice, company_xmlid: str, language: str) -> ET.Element:
    """``account.move`` as DRAFT. ``state='posted'`` must not be set in create()
    (UserError, verified account/models/account_move.py create()); posting happens
    in the post_init_hook via action_post(). journal_id/account_id are computed by
    the ORM (default journal of the matching type, accounts from product/category)
    - so only move_type/partner/date/lines are set. (verified-patterns.md 4.12)
    """
    line_dicts = []
    for line in inv.lines:
        line_dicts.append(
            "(0, 0, {"
            f"'product_id': ref('{line.product_xmlid}'), "
            f"'quantity': {line.qty}, "
            f"'price_unit': {line.price_unit}, "
            f"'name': {line.description!r}"
            "})"
        )
    fields = [
        field_el("move_type", text=inv.move_type),
        field_el("partner_id", ref=inv.partner_xmlid),
        field_el("invoice_date", text=inv.invoice_date),
        field_el("company_id", ref=company_xmlid),
    ]
    if inv.ref:
        fields.append(field_el("ref", text=inv.ref))
    fields.append(field_el("invoice_line_ids", model="account.move.line", eval_=f"[{', '.join(line_dicts)}]"))
    return record_el(
        "account.move",
        inv.xml_id,
        fields,
        context=_context(language, company_xmlid),
    )


def helpdesk_team_record(spec: CustomerSpec) -> ET.Element:
    fields = [
        field_el("name", text=spec.resolved_helpdesk_team_name),
        field_el("company_id", ref=spec.company.xml_id),
    ]
    return record_el("helpdesk.team", HELPDESK_TEAM_XMLID, fields, context=_context(spec.resolved_language))


def helpdesk_ticket_record(t: HelpdeskTicket, team_xmlid: str, company_xmlid: str, language: str) -> ET.Element:
    fields = [
        field_el("name", text=t.name),
        field_el("team_id", ref=team_xmlid),
        field_el("stage_id", ref=t.stage_xmlid),
    ]
    if t.partner_xmlid:
        fields.append(field_el("partner_id", ref=t.partner_xmlid))
    if t.priority is not None:
        fields.append(field_el("priority", text=t.priority))
    if t.description:
        fields.append(field_el("description", text=t.description))
    return record_el("helpdesk.ticket", t.xml_id, fields, context=_context(language))


def render_res_company_xml(spec: CustomerSpec) -> str:
    return render_odoo_file([company_record(spec.company, spec.resolved_language)])


def render_res_partner_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [partner_record(p, spec.company.xml_id, spec.resolved_language) for p in spec.partners]
    )


def render_product_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [product_record(p, spec.company.xml_id, spec.resolved_language) for p in spec.products]
    )


def render_mrp_bom_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [bom_record(b, spec.company.xml_id, spec.resolved_language) for b in spec.boms]
    )


def render_sale_order_quotation_xml(spec: CustomerSpec) -> str:
    assert spec.quotation is not None
    return render_odoo_file(
        [sale_order_record(spec.quotation, spec.company.xml_id, spec.resolved_language)]
    )


def render_sale_order_examples_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [sale_order_record(o, spec.company.xml_id, spec.resolved_language) for o in spec.example_orders],
        noupdate=True,
    )


def render_account_chart_xml(spec: CustomerSpec) -> str:
    return render_odoo_file([account_chart_function(spec)])


def render_crm_team_xml(spec: CustomerSpec) -> str:
    return render_odoo_file([crm_team_record(spec)])


def render_crm_lead_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [crm_lead_record(lead, spec.company.xml_id, CRM_TEAM_XMLID, spec.resolved_language)
         for lead in spec.crm_leads],
        noupdate=True,
    )


def render_purchase_order_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [purchase_order_record(o, spec.company.xml_id, spec.resolved_language)
         for o in spec.purchase_orders],
        noupdate=True,
    )


def render_stock_warehouse_xml(spec: CustomerSpec) -> str:
    return render_odoo_file([stock_warehouse_record(spec)])


def render_stock_quant_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [stock_quant_record(q, WAREHOUSE_XMLID, spec.resolved_language) for q in spec.stock_quants],
        noupdate=True,
    )


def render_account_move_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [account_move_record(inv, spec.company.xml_id, spec.resolved_language) for inv in spec.invoices],
        noupdate=True,
    )


def render_helpdesk_team_xml(spec: CustomerSpec) -> str:
    return render_odoo_file([helpdesk_team_record(spec)])


def render_helpdesk_ticket_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [helpdesk_ticket_record(t, HELPDESK_TEAM_XMLID, spec.company.xml_id, spec.resolved_language)
         for t in spec.helpdesk_tickets],
        noupdate=True,
    )

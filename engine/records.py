"""Builds the XML record elements from the dataclasses in model.py, exactly
following the patterns verified against the Odoo 20.0 source
(see skills/odoo-demo-data/reference/verified-patterns.md).

Each function here corresponds to a verified pattern. If a new field/behaviour
is needed that is not covered yet, do NOT simply add it: first verify it against
the Odoo 20.0 source and record the finding in verified-patterns.md.
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
    MaintenanceEquipment,
    MaintenanceEquipmentCategory,
    MaintenanceRequest,
    ManufacturingOrder,
    Partner,
    Product,
    Project,
    ProjectTask,
    ProjectTaskStage,
    PurchaseOrder,
    QualityAlert,
    QualityCheck,
    QualityPoint,
    QuotationTemplate,
    SaleOrder,
    StockQuant,
    Subscription,
)
from .xmlgen import field_el, record_el, render_odoo_file

# Fixed xml_ids for the per-company auto-created teams and the warehouse. Unique
# within a module because a module creates exactly one demo company.
CRM_TEAM_XMLID = "crm_team_demo"
HELPDESK_TEAM_XMLID = "helpdesk_team_demo"
MAINTENANCE_TEAM_XMLID = "maintenance_team_demo"
WAREHOUSE_XMLID = "warehouse_demo"

# Foreign xmlids (shipped by the apps, verified-patterns 4.24/4.25). The engine
# reuses them so no extra team/plan records are needed.
QUALITY_TEAM_XMLID = "quality.quality_alert_team0"
QUALITY_TEST_TYPE_XMLIDS = {
    "passfail": "quality_control.test_type_passfail",
    "measure": "quality_control.test_type_measure",
}
SUBSCRIPTION_PLAN_XMLIDS = {
    "month": "sale_subscription.subscription_plan_month",
    "year": "sale_subscription.subscription_plan_year",
}


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
    if p.recurring_invoice is not None:
        # product.template.recurring_invoice only exists with sale_subscription
        # (verified-patterns 4.25); validate.py rejects it without that dependency.
        fields.append(field_el("recurring_invoice", text=p.recurring_invoice))
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
        f"'uom_id': ref('{line.uom_xmlid}')"
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
        field_el("uom_id", ref=b.uom_xmlid),
        field_el("type", text="normal"),
        field_el("bom_line_ids", eval_=f"[{line_dicts}]"),
        field_el("company_id", ref=company_xmlid),
    ]
    return record_el("mrp.bom", b.xml_id, fields, context=_context(language))


def mrp_production_record(
    mo: ManufacturingOrder, company_xmlid: str, warehouse_xmlid: str, language: str
) -> ET.Element:
    """``mrp.production`` as a DRAFT manufacturing order (verified-patterns.md 4.17).

    ``state`` is compute+store+readonly in 20.0 and must NOT be set (a new MO is
    ``draft``). ``picking_type_id`` is required and its compute falls back to the
    company warehouse; it is set explicitly from the demo warehouse's
    manufacturing operation type (``stock.warehouse.manu_type_id``, added by mrp)
    so it cannot pick another company's operation type. ``uom_id`` and
    the locations are computed from product/BOM/operation type. No
    ``action_confirm`` -> no stock posting.
    """
    fields = [
        field_el("product_id", ref=mo.product_xmlid),
    ]
    if mo.bom_xmlid:
        fields.append(field_el("bom_id", ref=mo.bom_xmlid))
    fields += [
        field_el("product_qty", text=mo.qty),
        field_el("company_id", ref=company_xmlid),
        field_el(
            "picking_type_id",
            model="stock.warehouse",
            eval_=f"obj(ref('{warehouse_xmlid}')).manu_type_id.id",
        ),
    ]
    if mo.date_start:
        fields.append(field_el("date_start", text=mo.date_start))
    return record_el("mrp.production", mo.xml_id, fields, context=_context(language, company_xmlid))


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


def quotation_template_record(t: QuotationTemplate, company_xmlid: str, language: str) -> ET.Element:
    """``sale.order.template`` ("Angebotsvorlage", module sale_management).

    Verified against sale_management/models/sale_order_template{,_line}.py: only
    ``name`` is required; ``company_id`` is set explicitly so the template (and
    its product lines, ``_check_company_id``) belong to the demo company. The
    line's ``product_uom_id`` is set explicitly so the DB CHECK constraint
    ``_accountable_product_id_required`` (product_id AND product_uom_id NOT NULL)
    cannot race the compute (verified-patterns.md 4.20).
    """
    line_dicts = []
    for line in t.lines:
        parts = [
            f"'product_id': ref('{line.product_xmlid}')",
            f"'product_uom_qty': {line.qty}",
            "'product_uom_id': ref('uom.product_uom_unit')",
        ]
        if line.description:
            parts.append(f"'name': {line.description!r}")
        line_dicts.append("(0, 0, {" + ", ".join(parts) + "})")
    fields = [
        field_el("name", text=t.name),
        field_el("company_id", ref=company_xmlid),
        field_el("sequence", text=t.sequence),
    ]
    if t.note:
        fields.append(field_el("note", text=t.note))
    if t.number_of_days is not None:
        fields.append(field_el("number_of_days", text=t.number_of_days))
    fields.append(
        field_el("sale_order_template_line_ids", eval_=f"[{', '.join(line_dicts)}]")
    )
    return record_el("sale.order.template", t.xml_id, fields, context=_context(language, company_xmlid))


def project_task_stage_record(stage: ProjectTaskStage, language: str) -> ET.Element:
    """``project.task.type`` (task stage). No ``project_ids``/``user_id`` here:
    the stage is linked to its project through ``project.type_ids`` in
    ``project_record`` (the pattern of project/data/project_demo.xml), and
    ``project.task.type._compute_user_id`` then clears the default ``user_id``
    (verified-patterns.md 4.21)."""
    fields = [
        field_el("name", text=stage.name),
        field_el("sequence", text=stage.sequence),
        field_el("fold", text=stage.fold),
    ]
    return record_el("project.task.type", stage.xml_id, fields, context=_context(language))


def project_record(
    p: Project, company_xmlid: str, task_stage_xmlids: list[str], language: str
) -> ET.Element:
    """``project.project``. ``type_ids`` links the task stages to the project
    (the inverse ``project_ids`` is what ``project.task.stage_find`` searches);
    every defined task stage is linked so any task can reference any stage
    (verified-patterns.md 4.21). ``state``-like required fields have defaults."""
    fields = [
        field_el("name", text=p.name),
        field_el("company_id", ref=company_xmlid),
    ]
    if p.stage_xmlid:
        fields.append(field_el("stage_id", ref=p.stage_xmlid))
    if p.partner_xmlid:
        fields.append(field_el("partner_id", ref=p.partner_xmlid))
    if p.description:
        fields.append(field_el("description", text=p.description))
    if p.date_start:
        fields.append(field_el("date_start", text=p.date_start))
    if p.date_end:
        fields.append(field_el("date", text=p.date_end))
    if p.privacy_visibility:
        fields.append(field_el("privacy_visibility", text=p.privacy_visibility))
    link = ", ".join(f"Command.link(ref('{s}'))" for s in task_stage_xmlids)
    fields.append(field_el("type_ids", eval_=f"[{link}]"))
    return record_el("project.project", p.xml_id, fields, context=_context(language, company_xmlid))


def project_task_record(t: ProjectTask, company_xmlid: str, language: str) -> ET.Element:
    """``project.task``. ``state`` is compute+store+required and must NOT be set;
    ``stage_id`` is compute+store+readonly=False and must be a stage linked to
    the task's project, otherwise ``_compute_stage_id`` resets it
    (verified-patterns.md 4.21)."""
    fields = [
        field_el("name", text=t.name),
        field_el("project_id", ref=t.project_xmlid),
        field_el("company_id", ref=company_xmlid),
    ]
    if t.stage_xmlid:
        fields.append(field_el("stage_id", ref=t.stage_xmlid))
    if t.partner_xmlid:
        fields.append(field_el("partner_id", ref=t.partner_xmlid))
    if t.description:
        fields.append(field_el("description", text=t.description))
    if t.priority is not None:
        fields.append(field_el("priority", text=t.priority))
    if t.date_deadline:
        fields.append(field_el("date_deadline", text=t.date_deadline))
    if t.allocated_hours is not None:
        fields.append(field_el("allocated_hours", text=t.allocated_hours))
    return record_el("project.task", t.xml_id, fields, context=_context(language, company_xmlid))


# ---------------------------------------------------------------------------
# Maintenance (module `maintenance`, Community). Verified-patterns 4.22.
# ---------------------------------------------------------------------------


def maintenance_team_record(spec: CustomerSpec) -> ET.Element:
    """A ``maintenance.team`` for the demo company. ``maintenance.request.
    maintenance_team_id`` is required with a default that searches a team for the
    company; without a demo team it would fall back to another company's team
    (``check_company`` violation). Verified-patterns 4.22."""
    fields = [
        field_el("name", text=spec.resolved_maintenance_team_name),
        field_el("company_id", ref=spec.company.xml_id),
    ]
    return record_el("maintenance.team", MAINTENANCE_TEAM_XMLID, fields,
                     context=_context(spec.resolved_language))


def maintenance_equipment_category_record(
    category: MaintenanceEquipmentCategory, company_xmlid: str, language: str
) -> ET.Element:
    fields = [
        field_el("name", text=category.name),
        field_el("company_id", ref=company_xmlid),
    ]
    if category.note:
        fields.append(field_el("note", text=category.note))
    return record_el("maintenance.equipment.category", category.xml_id, fields,
                     context=_context(language))


def maintenance_equipment_record(
    e: MaintenanceEquipment, company_xmlid: str, language: str
) -> ET.Element:
    """``maintenance.equipment``. ``effective_date`` (required in the mixin) has a
    ``context_today`` default and is left to the ORM; ``serial_no`` is UNIQUE.
    Verified-patterns 4.22."""
    fields = [
        field_el("name", text=e.name),
        field_el("company_id", ref=company_xmlid),
        field_el("maintenance_team_id", ref=MAINTENANCE_TEAM_XMLID),
    ]
    if e.category_xmlid:
        fields.append(field_el("category_id", ref=e.category_xmlid))
    if e.partner_xmlid:
        fields.append(field_el("partner_id", ref=e.partner_xmlid))
    if e.serial_no:
        fields.append(field_el("serial_no", text=e.serial_no))
    if e.model:
        fields.append(field_el("model", text=e.model))
    if e.assign_date:
        fields.append(field_el("assign_date", text=e.assign_date))
    if e.warranty_date:
        fields.append(field_el("warranty_date", text=e.warranty_date))
    if e.cost is not None:
        fields.append(field_el("cost", text=e.cost))
    if e.note:
        fields.append(field_el("note", text=e.note))
    return record_el("maintenance.equipment", e.xml_id, fields, context=_context(language))


def maintenance_request_record(
    r: MaintenanceRequest, company_xmlid: str, language: str
) -> ET.Element:
    """``maintenance.request``. ``maintenance_team_id`` is set explicitly to the
    demo team (required, default searches by company). ``create()`` clears/fills
    ``close_date`` based on the stage's ``done`` flag. Verified-patterns 4.22."""
    fields = [
        field_el("name", text=r.name),
        field_el("company_id", ref=company_xmlid),
        field_el("maintenance_team_id", ref=MAINTENANCE_TEAM_XMLID),
        field_el("stage_id", ref=r.stage_xmlid),
        field_el("maintenance_type", text=r.maintenance_type),
    ]
    if r.equipment_xmlid:
        fields.append(field_el("equipment_id", ref=r.equipment_xmlid))
    if r.priority is not None:
        fields.append(field_el("priority", text=r.priority))
    if r.description:
        fields.append(field_el("description", text=r.description))
    if r.schedule_date:
        fields.append(field_el("schedule_date", text=r.schedule_date))
    if r.close_date:
        fields.append(field_el("close_date", text=r.close_date))
    return record_el("maintenance.request", r.xml_id, fields, context=_context(language))


# ---------------------------------------------------------------------------
# Quality control (app `quality_control`, Enterprise). Verified-patterns 4.24.
# ---------------------------------------------------------------------------


def quality_point_record(
    p: QualityPoint, company_xmlid: str, warehouse_xmlid: str, language: str
) -> ET.Element:
    """``quality.point``. ``picking_type_ids`` is required: the demo warehouse's
    manufacturing operation type (``manu_type_id``, added by mrp) is set so the
    point belongs to the demo company. ``team_id`` is the shipped global quality
    team. Verified-patterns 4.24."""
    fields = [
        field_el("name", text=p.name),
        field_el("company_id", ref=company_xmlid),
        field_el("team_id", ref=QUALITY_TEAM_XMLID),
        field_el("test_type_id", ref=QUALITY_TEST_TYPE_XMLIDS[p.test_type]),
        field_el("measure_on", text=p.measure_on),
        field_el("measure_frequency_type", text="all"),
        field_el(
            "picking_type_ids",
            model="stock.warehouse",
            eval_=f"[(6, 0, [obj(ref('{warehouse_xmlid}')).manu_type_id.id])]",
        ),
    ]
    if p.title:
        fields.append(field_el("title", text=p.title))
    if p.product_xmlids:
        refs = ", ".join(f"ref('{x}')" for x in p.product_xmlids)
        fields.append(field_el("product_ids", eval_=f"[(6, 0, [{refs}])]"))
    if p.note:
        fields.append(field_el("note", text=p.note))
    return record_el("quality.point", p.xml_id, fields, context=_context(language, company_xmlid))


def quality_check_record(
    c: QualityCheck, company_xmlid: str, language: str
) -> ET.Element:
    """``quality.check``. ``name`` is auto-filled from a sequence by ``create()``;
    ``team_id``/``test_type_id``/``measure_on``/``title``/``note`` are computed
    from ``point_id``. ``product_id`` must be the linked production order's
    finished product (``_check_allowed_product_ids_with_production``).
    Verified-patterns 4.24."""
    fields = [
        field_el("point_id", ref=c.point_xmlid),
        field_el("company_id", ref=company_xmlid),
        field_el("quality_state", text=c.quality_state),
    ]
    if c.production_xmlid:
        fields.append(field_el("production_id", ref=c.production_xmlid))
    if c.product_xmlid:
        fields.append(field_el("product_id", ref=c.product_xmlid))
    if c.note:
        fields.append(field_el("note", text=c.note))
    return record_el("quality.check", c.xml_id, fields, context=_context(language, company_xmlid))


def quality_alert_record(
    a: QualityAlert, company_xmlid: str, language: str
) -> ET.Element:
    """``quality.alert``. ``team_id`` is the shipped global team; ``stage_id``
    defaults to the shipped "New" stage. ``product_id`` is set directly (v20 has
    no ``product_tmpl_id`` on ``quality.alert``; ``production_id`` comes from
    ``quality_mrp``). Verified-patterns 4.24."""
    fields = [
        field_el("name", text=a.name),
        field_el("company_id", ref=company_xmlid),
        field_el("team_id", ref=QUALITY_TEAM_XMLID),
        field_el("stage_id", ref=a.stage_xmlid),
    ]
    if a.product_xmlid:
        fields.append(field_el("product_id", ref=a.product_xmlid))
    if a.partner_xmlid:
        fields.append(field_el("partner_id", ref=a.partner_xmlid))
    if a.production_xmlid:
        fields.append(field_el("production_id", ref=a.production_xmlid))
    if a.priority is not None:
        fields.append(field_el("priority", text=a.priority))
    if a.description:
        fields.append(field_el("description", text=a.description))
    return record_el("quality.alert", a.xml_id, fields, context=_context(language, company_xmlid))


# ---------------------------------------------------------------------------
# Subscriptions (app `sale_subscription`, Enterprise). Verified-patterns 4.25.
# ---------------------------------------------------------------------------


def subscription_record(s: Subscription, company_xmlid: str, language: str) -> ET.Element:
    """A subscription as a ``sale.order`` with ``plan_id`` (there is no
    ``sale.subscription`` model in 20.0). Created in ``state='draft'``: no
    invoices/pickings are generated and the plan/line constraint exempts drafts.
    ``is_subscription``/``subscription_state`` are computed and not set.
    Verified-patterns 4.25."""
    line_dicts = []
    for line in s.lines:
        parts = [
            f"'product_id': ref('{line.product_xmlid}')",
            f"'product_uom_qty': {line.qty}",
        ]
        if line.description:
            parts.append(f"'name': {line.description!r}")
        line_dicts.append("(0, 0, {" + ", ".join(parts) + "})")
    fields = [
        field_el("partner_id", ref=s.partner_xmlid),
        field_el("company_id", ref=company_xmlid),
        field_el("plan_id", ref=SUBSCRIPTION_PLAN_XMLIDS[s.plan]),
        field_el("state", text=s.state),
    ]
    if s.start_date:
        fields.append(field_el("start_date", text=s.start_date))
    fields.append(field_el("order_line", eval_=f"[{', '.join(line_dicts)}]"))
    return record_el("sale.order", s.xml_id, fields, context=_context(language))


# ---------------------------------------------------------------------------
# ERP building blocks (CRM, purchase, stock, accounting, helpdesk). Each object
# type was verified against the Odoo 20.0 source first (verified-patterns.md
# 4.9-4.15).
# ---------------------------------------------------------------------------


def account_chart_function(spec: CustomerSpec) -> ET.Element:
    """Loads the chart of accounts for the freshly created demo company.

    Verified pattern from account/demo/account_demo.xml (account 20.0):
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
            "'uom_id': ref('uom.product_uom_unit')",
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


def render_mrp_production_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [
            mrp_production_record(mo, spec.company.xml_id, WAREHOUSE_XMLID, spec.resolved_language)
            for mo in spec.manufacturing_orders
        ],
        noupdate=True,
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


def render_quotation_template_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [
            quotation_template_record(t, spec.company.xml_id, spec.resolved_language)
            for t in spec.quotation_templates
        ]
    )


def render_project_task_stage_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [project_task_stage_record(s, spec.resolved_language) for s in spec.project_task_stages]
    )


def render_project_xml(spec: CustomerSpec) -> str:
    task_stage_xmlids = [s.xml_id for s in spec.project_task_stages]
    return render_odoo_file(
        [
            project_record(p, spec.company.xml_id, task_stage_xmlids, spec.resolved_language)
            for p in spec.projects
        ],
        noupdate=True,
    )


def render_project_task_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [project_task_record(t, spec.company.xml_id, spec.resolved_language) for t in spec.project_tasks],
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


def render_maintenance_team_xml(spec: CustomerSpec) -> str:
    return render_odoo_file([maintenance_team_record(spec)])


def render_maintenance_equipment_category_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [maintenance_equipment_category_record(c, spec.company.xml_id, spec.resolved_language)
         for c in spec.maintenance_equipment_categories]
    )


def render_maintenance_equipment_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [maintenance_equipment_record(e, spec.company.xml_id, spec.resolved_language)
         for e in spec.maintenance_equipment],
        noupdate=True,
    )


def render_maintenance_request_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [maintenance_request_record(r, spec.company.xml_id, spec.resolved_language)
         for r in spec.maintenance_requests],
        noupdate=True,
    )


def render_quality_point_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [quality_point_record(p, spec.company.xml_id, WAREHOUSE_XMLID, spec.resolved_language)
         for p in spec.quality_points]
    )


def render_quality_check_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [quality_check_record(c, spec.company.xml_id, spec.resolved_language)
         for c in spec.quality_checks],
        noupdate=True,
    )


def render_quality_alert_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [quality_alert_record(a, spec.company.xml_id, spec.resolved_language)
         for a in spec.quality_alerts],
        noupdate=True,
    )


def render_subscription_xml(spec: CustomerSpec) -> str:
    return render_odoo_file(
        [subscription_record(s, spec.company.xml_id, spec.resolved_language)
         for s in spec.subscriptions],
        noupdate=True,
    )

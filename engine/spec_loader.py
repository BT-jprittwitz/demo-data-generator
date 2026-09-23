"""Loads a customer specification from a JSON dict into the dataclasses from model.py.

Deliberately no generic/"magic" mapping (e.g. **kwargs directly into the dataclass) -
every field is read explicitly so that a typo in the JSON yields a clear error message
instead of a TypeError from the dataclass constructor.
"""
from __future__ import annotations

import dataclasses
from typing import Any

from .model import (
    Bom,
    BomLine,
    Company,
    CrmLead,
    CustomerProfile,
    CustomerSpec,
    HelpdeskTicket,
    Invoice,
    InvoiceLine,
    MaintenanceEquipment,
    MaintenanceEquipmentCategory,
    MaintenanceRequest,
    ManufacturingOrder,
    Module,
    Partner,
    Product,
    Project,
    ProjectTask,
    ProjectTaskStage,
    PurchaseOrder,
    PurchaseOrderLine,
    QualityAlert,
    QualityCheck,
    QualityPoint,
    QuotationTemplate,
    QuotationTemplateLine,
    SaleOrder,
    SaleOrderLine,
    SpecError,
    StockQuant,
    Subscription,
    SubscriptionLine,
)


def _get(d: dict[str, Any], key: str, where: str, default=..., required=False):
    if key in d:
        return d[key]
    if required:
        raise SpecError(f"{where}: required field {key!r} is missing.")
    if default is ...:
        return None
    return default


def _reject_unknown(d: dict[str, Any], cls, where: str) -> None:
    """Rejects unknown fields. The allowed names come directly from the
    dataclass (single source of truth) - a typo in the JSON is thus reported
    immediately instead of being silently ignored."""
    allowed = {f.name for f in dataclasses.fields(cls)}
    unknown = set(d) - allowed
    if unknown:
        raise SpecError(
            f"{where}: unknown fields {sorted(unknown)}. Allowed: {sorted(allowed)}."
        )


def _checked(d: dict[str, Any], cls, where: str) -> dict[str, Any]:
    _reject_unknown(d, cls, where)
    return d


def _as_records(value: Any, where: str) -> list[dict[str, Any]]:
    """Normalise a record list to a list of dicts.

    Accepts either the verbose form (a list of objects) or a **compact table**:
    a list whose first element is a header row of field names and whose remaining
    elements are value rows of equal length, e.g.

        "partners": [
          ["xml_id", "name", "country_xmlid", "street", "city", "zip"],
          ["p_c1", "Autohaus Vogel GmbH", "base.de", "Karlstrasse 100", "Karlsruhe", "76133"]
        ]

    The table form removes the repeated keys (a large token saving for the LLM
    author) without changing the parsed result. Values keep their JSON type.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise SpecError(
            f"{where}: expected a list of records (objects, or a table = header "
            f"row + data rows), got {type(value).__name__}."
        )
    if not value:
        return []
    first = value[0]
    if isinstance(first, dict):
        return value
    if isinstance(first, list):
        header = first
        if not all(isinstance(h, str) for h in header):
            raise SpecError(f"{where}: table header must be a list of field-name strings.")
        records: list[dict[str, Any]] = []
        for index, row in enumerate(value[1:], start=1):
            if not isinstance(row, list):
                raise SpecError(f"{where}: table row {index} is not a list.")
            if len(row) != len(header):
                raise SpecError(
                    f"{where}: table row {index} has {len(row)} value(s), but the "
                    f"header has {len(header)} column(s)."
                )
            records.append(dict(zip(header, row)))
        return records
    raise SpecError(
        f"{where}: records must be objects; the first element is {type(first).__name__}."
    )


def load_customer_profile(d: dict[str, Any]) -> CustomerProfile:
    _reject_unknown(d, CustomerProfile, "customer_profile")
    return CustomerProfile(
        industry=_get(d, "industry", "customer_profile", default=None),
        business_model=_get(d, "business_model", "customer_profile", default=None),
        product_domains=_get(d, "product_domains", "customer_profile", default=[]),
        customer_segments=_get(d, "customer_segments", "customer_profile", default=[]),
        region=_get(d, "region", "customer_profile", default=None),
    )


def load_module(d: dict[str, Any]) -> Module:
    _reject_unknown(d, Module, "module")
    return Module(
        technical_name=_get(d, "technical_name", "module", required=True),
        title=_get(d, "title", "module", required=True),
        summary=_get(d, "summary", "module", required=True),
        description=_get(d, "description", "module", default=""),
        category=_get(d, "category", "module", default="Sales"),
    )


def load_company(d: dict[str, Any]) -> Company:
    _reject_unknown(d, Company, "company")
    return Company(
        xml_id=_get(d, "xml_id", "company", default="demo_company"),
        name=_get(d, "name", "company", required=True),
        street=_get(d, "street", "company", required=True),
        city=_get(d, "city", "company", required=True),
        zip=_get(d, "zip", "company", required=True),
        country_xmlid=_get(d, "country_xmlid", "company", required=True),
        vat=_get(d, "vat", "company", default=None),
        currency_xmlid=_get(d, "currency_xmlid", "company", default=None),
        chart_template=_get(d, "chart_template", "company", default=None),
    )


def load_partner(d: dict[str, Any]) -> Partner:
    xml_id = _get(d, "xml_id", "partner", required=True)
    _reject_unknown(d, Partner, f"partner {xml_id}")
    return Partner(
        xml_id=xml_id,
        name=_get(d, "name", f"partner {xml_id}", required=True),
        country_xmlid=_get(d, "country_xmlid", f"partner {xml_id}", required=True),
        street=_get(d, "street", f"partner {xml_id}", required=True),
        city=_get(d, "city", f"partner {xml_id}", required=True),
        zip=_get(d, "zip", f"partner {xml_id}", required=True),
        vat=_get(d, "vat", f"partner {xml_id}", default=None),
        is_company=_get(d, "is_company", f"partner {xml_id}", default=True),
        supplier_rank=_get(d, "supplier_rank", f"partner {xml_id}", default=0),
        customer_rank=_get(d, "customer_rank", f"partner {xml_id}", default=1),
    )


def load_product(d: dict[str, Any]) -> Product:
    xml_id = _get(d, "xml_id", "product", required=True)
    where = f"product {xml_id}"
    _reject_unknown(d, Product, where)
    return Product(
        xml_id=xml_id,
        name=_get(d, "name", where, required=True),
        type=_get(d, "type", where, required=True),
        sale_ok=_get(d, "sale_ok", where, required=True),
        purchase_ok=_get(d, "purchase_ok", where, required=True),
        list_price=_get(d, "list_price", where, default=0.0),
        standard_price=_get(d, "standard_price", where, default=None),
        is_storable=_get(d, "is_storable", where, default=None),
        default_code=_get(d, "default_code", where, default=None),
        barcode=_get(d, "barcode", where, default=None),
        weight=_get(d, "weight", where, default=None),
        volume=_get(d, "volume", where, default=None),
        description_sale=_get(d, "description_sale", where, default=None),
        recurring_invoice=_get(d, "recurring_invoice", where, default=None),
    )


def load_bom(d: dict[str, Any]) -> Bom:
    xml_id = _get(d, "xml_id", "bom", required=True)
    where = f"bom {xml_id}"
    _reject_unknown(d, Bom, where)
    lines_raw = _as_records(_get(d, "lines", where, required=True), f"{where} lines")
    lines = [
        BomLine(
            product_xmlid=_get(ld, "product_xmlid", f"{where} line", required=True),
            qty=_get(ld, "qty", f"{where} line", required=True),
            uom_xmlid=_get(ld, "uom_xmlid", f"{where} line", default="uom.product_uom_unit"),
        )
        for ld in [_checked(x, BomLine, f"{where} line") for x in lines_raw]
    ]
    return Bom(
        xml_id=xml_id,
        product_xmlid=_get(d, "product_xmlid", where, required=True),
        lines=lines,
        qty=_get(d, "qty", where, default=1.0),
        uom_xmlid=_get(d, "uom_xmlid", where, default="uom.product_uom_unit"),
    )


def load_manufacturing_order(d: dict[str, Any]) -> ManufacturingOrder:
    xml_id = _get(d, "xml_id", "manufacturing_order", required=True)
    where = f"manufacturing_order {xml_id}"
    _reject_unknown(d, ManufacturingOrder, where)
    return ManufacturingOrder(
        xml_id=xml_id,
        product_xmlid=_get(d, "product_xmlid", where, required=True),
        qty=_get(d, "qty", where, required=True),
        bom_xmlid=_get(d, "bom_xmlid", where, default=None),
        date_start=_get(d, "date_start", where, default=None),
    )


def load_sale_order(d: dict[str, Any]) -> SaleOrder:
    xml_id = _get(d, "xml_id", "sale_order", required=True)
    where = f"sale_order {xml_id}"
    _reject_unknown(d, SaleOrder, where)
    lines_raw = _as_records(_get(d, "lines", where, required=True), f"{where} lines")
    lines = [
        SaleOrderLine(
            product_xmlid=_get(ld, "product_xmlid", f"{where} line", required=True),
            qty=_get(ld, "qty", f"{where} line", required=True),
            description=_get(ld, "description", f"{where} line", required=True),
        )
        for ld in [_checked(x, SaleOrderLine, f"{where} line") for x in lines_raw]
    ]
    return SaleOrder(
        xml_id=xml_id,
        partner_xmlid=_get(d, "partner_xmlid", where, required=True),
        lines=lines,
        state=_get(d, "state", where, default="sent"),
        date_order=_get(d, "date_order", where, default=None),
    )


def load_quotation_template(d: dict[str, Any]) -> QuotationTemplate:
    xml_id = _get(d, "xml_id", "quotation_template", required=True)
    where = f"quotation_template {xml_id}"
    _reject_unknown(d, QuotationTemplate, where)
    lines_raw = _as_records(_get(d, "lines", where, required=True), f"{where} lines")
    lines = [
        QuotationTemplateLine(
            product_xmlid=_get(ld, "product_xmlid", f"{where} line", required=True),
            qty=_get(ld, "qty", f"{where} line", default=1.0),
            description=_get(ld, "description", f"{where} line", default=None),
        )
        for ld in [_checked(x, QuotationTemplateLine, f"{where} line") for x in lines_raw]
    ]
    return QuotationTemplate(
        xml_id=xml_id,
        name=_get(d, "name", where, required=True),
        lines=lines,
        note=_get(d, "note", where, default=None),
        number_of_days=_get(d, "number_of_days", where, default=None),
        sequence=_get(d, "sequence", where, default=10),
    )


def load_crm_lead(d: dict[str, Any]) -> CrmLead:
    xml_id = _get(d, "xml_id", "crm_lead", required=True)
    where = f"crm_lead {xml_id}"
    _reject_unknown(d, CrmLead, where)
    return CrmLead(
        xml_id=xml_id,
        name=_get(d, "name", where, required=True),
        type=_get(d, "type", where, default="opportunity"),
        partner_xmlid=_get(d, "partner_xmlid", where, default=None),
        contact_name=_get(d, "contact_name", where, default=None),
        email_from=_get(d, "email_from", where, default=None),
        phone=_get(d, "phone", where, default=None),
        expected_revenue=_get(d, "expected_revenue", where, default=None),
        probability=_get(d, "probability", where, default=None),
        stage_xmlid=_get(d, "stage_xmlid", where, default="crm.stage_lead1"),
        description=_get(d, "description", where, default=None),
        priority=_get(d, "priority", where, default=None),
    )


def load_purchase_order(d: dict[str, Any]) -> PurchaseOrder:
    xml_id = _get(d, "xml_id", "purchase_order", required=True)
    where = f"purchase_order {xml_id}"
    _reject_unknown(d, PurchaseOrder, where)
    lines_raw = _as_records(_get(d, "lines", where, required=True), f"{where} lines")
    lines = [
        PurchaseOrderLine(
            product_xmlid=_get(ld, "product_xmlid", f"{where} line", required=True),
            qty=_get(ld, "qty", f"{where} line", required=True),
            price_unit=_get(ld, "price_unit", f"{where} line", required=True),
            description=_get(ld, "description", f"{where} line", required=True),
            date_planned=_get(ld, "date_planned", f"{where} line", default=None),
        )
        for ld in [_checked(x, PurchaseOrderLine, f"{where} line") for x in lines_raw]
    ]
    return PurchaseOrder(
        xml_id=xml_id,
        partner_xmlid=_get(d, "partner_xmlid", where, required=True),
        lines=lines,
        state=_get(d, "state", where, default="draft"),
        date_order=_get(d, "date_order", where, default=None),
        partner_ref=_get(d, "partner_ref", where, default=None),
    )


def load_stock_quant(d: dict[str, Any]) -> StockQuant:
    product_xmlid = _get(d, "product_xmlid", "stock_quant", required=True)
    _reject_unknown(d, StockQuant, f"stock_quant {product_xmlid}")
    return StockQuant(
        product_xmlid=product_xmlid,
        qty=_get(d, "qty", f"stock_quant {product_xmlid}", required=True),
    )


def load_invoice(d: dict[str, Any]) -> Invoice:
    xml_id = _get(d, "xml_id", "invoice", required=True)
    where = f"invoice {xml_id}"
    _reject_unknown(d, Invoice, where)
    lines_raw = _as_records(_get(d, "lines", where, required=True), f"{where} lines")
    lines = [
        InvoiceLine(
            product_xmlid=_get(ld, "product_xmlid", f"{where} line", required=True),
            qty=_get(ld, "qty", f"{where} line", required=True),
            price_unit=_get(ld, "price_unit", f"{where} line", required=True),
            description=_get(ld, "description", f"{where} line", required=True),
        )
        for ld in [_checked(x, InvoiceLine, f"{where} line") for x in lines_raw]
    ]
    return Invoice(
        xml_id=xml_id,
        move_type=_get(d, "move_type", where, required=True),
        partner_xmlid=_get(d, "partner_xmlid", where, required=True),
        invoice_date=_get(d, "invoice_date", where, required=True),
        lines=lines,
        ref=_get(d, "ref", where, default=None),
    )


def load_helpdesk_ticket(d: dict[str, Any]) -> HelpdeskTicket:
    xml_id = _get(d, "xml_id", "helpdesk_ticket", required=True)
    where = f"helpdesk_ticket {xml_id}"
    _reject_unknown(d, HelpdeskTicket, where)
    return HelpdeskTicket(
        xml_id=xml_id,
        name=_get(d, "name", where, required=True),
        partner_xmlid=_get(d, "partner_xmlid", where, default=None),
        stage_xmlid=_get(d, "stage_xmlid", where, default="helpdesk.stage_new"),
        priority=_get(d, "priority", where, default=None),
        description=_get(d, "description", where, default=None),
    )


def load_project_stage(d: dict[str, Any]) -> ProjectTaskStage:
    xml_id = _get(d, "xml_id", "project_task_stage", required=True)
    where = f"project_task_stage {xml_id}"
    _reject_unknown(d, ProjectTaskStage, where)
    return ProjectTaskStage(
        xml_id=xml_id,
        name=_get(d, "name", where, required=True),
        sequence=_get(d, "sequence", where, default=10),
        fold=_get(d, "fold", where, default=False),
    )


def load_project(d: dict[str, Any]) -> Project:
    xml_id = _get(d, "xml_id", "project", required=True)
    where = f"project {xml_id}"
    _reject_unknown(d, Project, where)
    return Project(
        xml_id=xml_id,
        name=_get(d, "name", where, required=True),
        stage_xmlid=_get(d, "stage_xmlid", where, default=None),
        partner_xmlid=_get(d, "partner_xmlid", where, default=None),
        description=_get(d, "description", where, default=None),
        date_start=_get(d, "date_start", where, default=None),
        date_end=_get(d, "date_end", where, default=None),
        privacy_visibility=_get(d, "privacy_visibility", where, default=None),
        is_fsm=_get(d, "is_fsm", where, default=False),
    )


def load_project_task(d: dict[str, Any]) -> ProjectTask:
    xml_id = _get(d, "xml_id", "project_task", required=True)
    where = f"project_task {xml_id}"
    _reject_unknown(d, ProjectTask, where)
    return ProjectTask(
        xml_id=xml_id,
        name=_get(d, "name", where, required=True),
        project_xmlid=_get(d, "project_xmlid", where, required=True),
        stage_xmlid=_get(d, "stage_xmlid", where, default=None),
        partner_xmlid=_get(d, "partner_xmlid", where, default=None),
        description=_get(d, "description", where, default=None),
        priority=_get(d, "priority", where, default=None),
        date_deadline=_get(d, "date_deadline", where, default=None),
        allocated_hours=_get(d, "allocated_hours", where, default=None),
    )


def load_maintenance_equipment_category(d: dict[str, Any]) -> MaintenanceEquipmentCategory:
    xml_id = _get(d, "xml_id", "maintenance_equipment_category", required=True)
    where = f"maintenance_equipment_category {xml_id}"
    _reject_unknown(d, MaintenanceEquipmentCategory, where)
    return MaintenanceEquipmentCategory(
        xml_id=xml_id,
        name=_get(d, "name", where, required=True),
        note=_get(d, "note", where, default=None),
    )


def load_maintenance_equipment(d: dict[str, Any]) -> MaintenanceEquipment:
    xml_id = _get(d, "xml_id", "maintenance_equipment", required=True)
    where = f"maintenance_equipment {xml_id}"
    _reject_unknown(d, MaintenanceEquipment, where)
    return MaintenanceEquipment(
        xml_id=xml_id,
        name=_get(d, "name", where, required=True),
        category_xmlid=_get(d, "category_xmlid", where, default=None),
        partner_xmlid=_get(d, "partner_xmlid", where, default=None),
        serial_no=_get(d, "serial_no", where, default=None),
        model=_get(d, "model", where, default=None),
        assign_date=_get(d, "assign_date", where, default=None),
        warranty_date=_get(d, "warranty_date", where, default=None),
        cost=_get(d, "cost", where, default=None),
        note=_get(d, "note", where, default=None),
    )


def load_maintenance_request(d: dict[str, Any]) -> MaintenanceRequest:
    xml_id = _get(d, "xml_id", "maintenance_request", required=True)
    where = f"maintenance_request {xml_id}"
    _reject_unknown(d, MaintenanceRequest, where)
    return MaintenanceRequest(
        xml_id=xml_id,
        name=_get(d, "name", where, required=True),
        equipment_xmlid=_get(d, "equipment_xmlid", where, default=None),
        maintenance_type=_get(d, "maintenance_type", where, default="corrective"),
        stage_xmlid=_get(d, "stage_xmlid", where, default="maintenance.stage_0"),
        priority=_get(d, "priority", where, default=None),
        description=_get(d, "description", where, default=None),
        request_date=_get(d, "request_date", where, default=None),
        schedule_date=_get(d, "schedule_date", where, default=None),
        close_date=_get(d, "close_date", where, default=None),
    )


def load_quality_point(d: dict[str, Any]) -> QualityPoint:
    xml_id = _get(d, "xml_id", "quality_point", required=True)
    where = f"quality_point {xml_id}"
    _reject_unknown(d, QualityPoint, where)
    return QualityPoint(
        xml_id=xml_id,
        name=_get(d, "name", where, required=True),
        title=_get(d, "title", where, default=None),
        product_xmlids=_get(d, "product_xmlids", where, default=[]),
        test_type=_get(d, "test_type", where, default="passfail"),
        measure_on=_get(d, "measure_on", where, default="product"),
        note=_get(d, "note", where, default=None),
    )


def load_quality_check(d: dict[str, Any]) -> QualityCheck:
    xml_id = _get(d, "xml_id", "quality_check", required=True)
    where = f"quality_check {xml_id}"
    _reject_unknown(d, QualityCheck, where)
    return QualityCheck(
        xml_id=xml_id,
        point_xmlid=_get(d, "point_xmlid", where, required=True),
        production_xmlid=_get(d, "production_xmlid", where, default=None),
        product_xmlid=_get(d, "product_xmlid", where, default=None),
        quality_state=_get(d, "quality_state", where, default="none"),
        note=_get(d, "note", where, default=None),
    )


def load_quality_alert(d: dict[str, Any]) -> QualityAlert:
    xml_id = _get(d, "xml_id", "quality_alert", required=True)
    where = f"quality_alert {xml_id}"
    _reject_unknown(d, QualityAlert, where)
    return QualityAlert(
        xml_id=xml_id,
        name=_get(d, "name", where, required=True),
        product_xmlid=_get(d, "product_xmlid", where, default=None),
        partner_xmlid=_get(d, "partner_xmlid", where, default=None),
        production_xmlid=_get(d, "production_xmlid", where, default=None),
        stage_xmlid=_get(d, "stage_xmlid", where, default="quality.quality_alert_stage_0"),
        priority=_get(d, "priority", where, default=None),
        description=_get(d, "description", where, default=None),
    )


def load_subscription(d: dict[str, Any]) -> Subscription:
    xml_id = _get(d, "xml_id", "subscription", required=True)
    where = f"subscription {xml_id}"
    _reject_unknown(d, Subscription, where)
    lines_raw = _as_records(_get(d, "lines", where, required=True), f"{where} lines")
    lines = [
        SubscriptionLine(
            product_xmlid=_get(ld, "product_xmlid", f"{where} line", required=True),
            qty=_get(ld, "qty", f"{where} line", default=1.0),
            description=_get(ld, "description", f"{where} line", default=None),
        )
        for ld in [_checked(x, SubscriptionLine, f"{where} line") for x in lines_raw]
    ]
    return Subscription(
        xml_id=xml_id,
        partner_xmlid=_get(d, "partner_xmlid", where, required=True),
        plan=_get(d, "plan", where, default="month"),
        state=_get(d, "state", where, default="draft"),
        start_date=_get(d, "start_date", where, default=None),
        lines=lines,
    )


def load_spec(d: dict[str, Any]) -> CustomerSpec:
    _reject_unknown(d, CustomerSpec, "spec")
    if "module" not in d:
        raise SpecError("spec: required field 'module' is missing.")
    if "company" not in d:
        raise SpecError("spec: required field 'company' is missing.")
    quotation_raw = d.get("quotation")

    def rows(key: str) -> list[dict[str, Any]]:
        return _as_records(d.get(key, []), key)

    return CustomerSpec(
        module=load_module(d["module"]),
        company=load_company(d["company"]),
        partners=[load_partner(p) for p in rows("partners")],
        products=[load_product(p) for p in rows("products")],
        boms=[load_bom(b) for b in rows("boms")],
        manufacturing_orders=[load_manufacturing_order(x) for x in rows("manufacturing_orders")],
        quotation=load_sale_order(quotation_raw) if quotation_raw else None,
        example_orders=[load_sale_order(o) for o in rows("example_orders")],
        crm_leads=[load_crm_lead(x) for x in rows("crm_leads")],
        purchase_orders=[load_purchase_order(x) for x in rows("purchase_orders")],
        stock_quants=[load_stock_quant(x) for x in rows("stock_quants")],
        invoices=[load_invoice(x) for x in rows("invoices")],
        helpdesk_tickets=[load_helpdesk_ticket(x) for x in rows("helpdesk_tickets")],
        quotation_templates=[load_quotation_template(x) for x in rows("quotation_templates")],
        projects=[load_project(x) for x in rows("projects")],
        project_task_stages=[load_project_stage(x) for x in rows("project_task_stages")],
        project_tasks=[load_project_task(x) for x in rows("project_tasks")],
        maintenance_equipment_categories=[
            load_maintenance_equipment_category(x)
            for x in rows("maintenance_equipment_categories")
        ],
        maintenance_equipment=[load_maintenance_equipment(x) for x in rows("maintenance_equipment")],
        maintenance_requests=[load_maintenance_request(x) for x in rows("maintenance_requests")],
        quality_points=[load_quality_point(x) for x in rows("quality_points")],
        quality_checks=[load_quality_check(x) for x in rows("quality_checks")],
        quality_alerts=[load_quality_alert(x) for x in rows("quality_alerts")],
        subscriptions=[load_subscription(x) for x in rows("subscriptions")],
        language=_get(d, "language", "spec", default=None),
        crm_team_name=_get(d, "crm_team_name", "spec", default=None),
        helpdesk_team_name=_get(d, "helpdesk_team_name", "spec", default=None),
        accounting_app=_get(d, "accounting_app", "spec", default="full"),
        customer_profile=(
            load_customer_profile(d["customer_profile"])
            if d.get("customer_profile")
            else None
        ),
    )

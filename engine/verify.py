"""Spec-aware Postgres assertions for the installation smoke test.

The log alone is not proof: Odoo prints ``Module <name> loaded`` even when a
``post_init_hook`` swallowed an exception (e.g. a failed invoice posting), and a
harmless line containing "Traceback" is a false positive. This module derives,
purely from the spec, SQL checks that verify the expected records really exist in
Postgres. Every generated record carries an xmlid, hence a row in
``ir_model_data`` - counting those is robust (no per-table column knowledge) and
verifies that the XML load actually persisted the data.

See skills/odoo-demo-data/reference/install-test-protocol.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from .model import CustomerSpec


@dataclass(frozen=True)
class DataCheck:
    """One SQL scalar assertion.

    ``sql`` must return a single value (int or text) when run with
    ``psql -tAc``. ``expected`` is the expected integer (or the string form).
    """

    label: str
    expected: object
    sql: str
    hint: str = ""


def company_id_query(spec: CustomerSpec) -> str:
    """SQL returning the demo company's res_id (used for company_dependent checks)."""
    module = spec.module.technical_name
    return (
        "SELECT res_id FROM ir_model_data "
        f"WHERE module = '{module}' AND name = '{spec.company.xml_id}' "
        "AND model = 'res.company';"
    )


def data_checks(spec: CustomerSpec) -> list[DataCheck]:
    """Expected record counts and a few semantic checks, derived from the spec.

    Counts go through ``ir_model_data`` (one row per generated xmlid). Sections
    with no records are skipped, except ``company`` which must always exist.
    """
    module = spec.module.technical_name
    checks: list[DataCheck] = []

    def count_xmlids(label: str, model: str, expected: int, hint: str = "") -> None:
        checks.append(
            DataCheck(
                label=label,
                expected=expected,
                sql=(
                    "SELECT count(*) FROM ir_model_data "
                    f"WHERE module = '{module}' AND model = '{model}';"
                ),
                hint=hint,
            )
        )

    count_xmlids("company", "res.company", 1, "the demo company was not created")
    if spec.partners:
        count_xmlids("partners", "res.partner", len(spec.partners))
    if spec.products:
        count_xmlids("products", "product.product", len(spec.products))
    if spec.boms:
        count_xmlids("boms", "mrp.bom", len(spec.boms))
    if spec.manufacturing_orders:
        count_xmlids("manufacturing_orders", "mrp.production", len(spec.manufacturing_orders))
    sale_orders = len(spec.example_orders) + (1 if spec.quotation else 0) + len(spec.subscriptions)
    if sale_orders:
        count_xmlids("sale_orders", "sale.order", sale_orders)
    if spec.subscriptions:
        checks.append(
            DataCheck(
                label="subscriptions_with_plan",
                expected=len(spec.subscriptions),
                sql=(
                    "SELECT count(*) FROM sale_order so "
                    "JOIN ir_model_data d ON d.model = 'sale.order' AND d.res_id = so.id "
                    f"WHERE d.module = '{module}' AND so.plan_id IS NOT NULL;"
                ),
                hint="plan_id was not stored - is sale_subscription installed?",
            )
        )
    if spec.quotation_templates:
        count_xmlids("quotation_templates", "sale.order.template", len(spec.quotation_templates))
    if spec.crm_leads:
        count_xmlids("crm_leads", "crm.lead", len(spec.crm_leads))
    if spec.purchase_orders:
        count_xmlids("purchase_orders", "purchase.order", len(spec.purchase_orders))
    if spec.stock_quants:
        count_xmlids("stock_quants", "stock.quant", len(spec.stock_quants))
    if spec.invoices:
        count_xmlids("invoices", "account.move", len(spec.invoices))
        checks.append(
            DataCheck(
                label="invoices_posted",
                expected=len(spec.invoices),
                sql=(
                    "SELECT count(*) FROM account_move am "
                    "JOIN ir_model_data d ON d.model = 'account.move' AND d.res_id = am.id "
                    f"WHERE d.module = '{module}' AND am.state = 'posted';"
                ),
                hint="post_init_hook posting failed (error was swallowed)",
            )
        )
    if spec.helpdesk_tickets:
        count_xmlids("helpdesk_tickets", "helpdesk.ticket", len(spec.helpdesk_tickets))
    if spec.projects:
        count_xmlids("projects", "project.project", len(spec.projects))
    if spec.project_task_stages:
        count_xmlids("project_task_stages", "project.task.type", len(spec.project_task_stages))
    if spec.project_tasks:
        count_xmlids("project_tasks", "project.task", len(spec.project_tasks))
        # Only tasks that declare a stage are checked, and each must have kept its
        # declared stage: project.task._compute_stage_id resets a stage that is
        # not linked to the project (verified-patterns 4.21). FSM tasks declare no
        # stage and legitimately receive the project's default stage, so they are
        # excluded.
        staged_tasks = [t for t in spec.project_tasks if t.stage_xmlid]
        if staged_tasks:
            values = ", ".join(f"('{t.xml_id}', '{t.stage_xmlid}')" for t in staged_tasks)
            checks.append(
                DataCheck(
                    label="project_tasks_with_declared_stage",
                    expected=len(staged_tasks),
                    sql=(
                        "SELECT count(*) FROM project_task pt "
                        "JOIN ir_model_data d ON d.model = 'project.task' AND d.res_id = pt.id "
                        "JOIN ir_model_data ds ON ds.model = 'project.task.type' "
                        "AND ds.res_id = pt.stage_id "
                        f"JOIN (VALUES {values}) AS expected(task_name, stage_name) "
                        "ON d.name = expected.task_name AND ds.name = expected.stage_name "
                        f"WHERE d.module = '{module}' AND ds.module = '{module}';"
                    ),
                    hint="a task's stage was reset - is it linked to the project (type_ids)?",
                )
            )
    if spec.maintenance_equipment_categories:
        count_xmlids("maintenance_equipment_categories", "maintenance.equipment.category",
                     len(spec.maintenance_equipment_categories))
    if spec.maintenance_equipment:
        count_xmlids("maintenance_equipment", "maintenance.equipment", len(spec.maintenance_equipment))
    if spec.maintenance_requests:
        count_xmlids("maintenance_requests", "maintenance.request", len(spec.maintenance_requests))
    if spec.quality_points:
        count_xmlids("quality_points", "quality.point", len(spec.quality_points))
    if spec.quality_checks:
        count_xmlids("quality_checks", "quality.check", len(spec.quality_checks))
    if spec.quality_alerts:
        count_xmlids("quality_alerts", "quality.alert", len(spec.quality_alerts))
    recurring = [p for p in spec.products if p.recurring_invoice]
    if recurring:
        checks.append(
            DataCheck(
                label="products_recurring_invoice",
                expected=len(recurring),
                sql=(
                    "SELECT count(*) FROM product_product pp "
                    "JOIN product_template pt ON pt.id = pp.product_tmpl_id "
                    "JOIN ir_model_data d ON d.model = 'product.product' AND d.res_id = pp.id "
                    f"WHERE d.module = '{module}' AND pt.recurring_invoice;"
                ),
                hint="recurring_invoice was not stored - is sale_subscription installed?",
            )
        )
    return checks


def standard_price_check(spec: CustomerSpec, company_id: int) -> DataCheck | None:
    """Verify that ``standard_price`` (company_dependent) is stored for the demo
    company, not for the installation company (verified-patterns.md 4.7).

    The value lives as jsonb ``{"<company_id>": <value>}`` on product_product;
    the check counts our products that have the demo company as a key. Only
    meaningful when at least one product sets ``standard_price``.
    """
    with_price = [p for p in spec.products if p.standard_price is not None]
    if not with_price:
        return None
    module = spec.module.technical_name
    return DataCheck(
        label="products_standard_price_company_key",
        expected=len(with_price),
        sql=(
            "SELECT count(*) FROM product_product pp "
            "JOIN ir_model_data d ON d.model = 'product.product' AND d.res_id = pp.id "
            f"WHERE d.module = '{module}' AND pp.standard_price ? '{company_id}';"
        ),
        hint=(
            "standard_price (company_dependent) not stored for the demo company - "
            "check context {'allowed_company_ids': [...]} (verified-patterns.md 4.7)"
        ),
    )

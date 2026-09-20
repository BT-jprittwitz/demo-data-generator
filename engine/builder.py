"""Builds an installable Odoo module from a CustomerSpec: first as a
directory tree, then as a ZIP."""
from __future__ import annotations

import zipfile
from pathlib import Path

from . import records
from .manifest import render_hooks_py, render_init_py, render_manifest
from .model import CustomerSpec


def write_module_dir(spec: CustomerSpec, out_dir: Path) -> Path:
    module_dir = out_dir / spec.module.technical_name
    data_dir = module_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    (module_dir / "__manifest__.py").write_text(render_manifest(spec), encoding="utf-8")
    (module_dir / "__init__.py").write_text(render_init_py(), encoding="utf-8")
    (module_dir / "hooks.py").write_text(render_hooks_py(spec), encoding="utf-8")

    (data_dir / "res_company_data.xml").write_text(records.render_res_company_xml(spec), encoding="utf-8")
    # The chart of accounts MUST be loaded before products and invoices.
    if spec.company.chart_template:
        (data_dir / "account_chart_data.xml").write_text(records.render_account_chart_xml(spec), encoding="utf-8")
    if spec.crm_leads:
        (data_dir / "crm_team_data.xml").write_text(records.render_crm_team_xml(spec), encoding="utf-8")
    if spec.helpdesk_tickets:
        (data_dir / "helpdesk_team_data.xml").write_text(records.render_helpdesk_team_xml(spec), encoding="utf-8")
    if spec.partners:
        (data_dir / "res_partner_data.xml").write_text(records.render_res_partner_xml(spec), encoding="utf-8")
    # Task stages MUST exist before the projects that link them (type_ids).
    if spec.project_task_stages:
        (data_dir / "project_task_stage_data.xml").write_text(
            records.render_project_task_stage_xml(spec), encoding="utf-8"
        )
    if spec.projects:
        (data_dir / "project_project_data.xml").write_text(
            records.render_project_xml(spec), encoding="utf-8"
        )
    if spec.project_tasks:
        (data_dir / "project_task_data.xml").write_text(
            records.render_project_task_xml(spec), encoding="utf-8"
        )
    if spec.products:
        (data_dir / "product_data.xml").write_text(records.render_product_xml(spec), encoding="utf-8")
    if spec.boms:
        (data_dir / "mrp_bom_data.xml").write_text(records.render_mrp_bom_xml(spec), encoding="utf-8")
    # The warehouse MUST exist before purchasing and stock (purchase_stock picking_type_id).
    if spec.needs_warehouse:
        (data_dir / "stock_warehouse_data.xml").write_text(records.render_stock_warehouse_xml(spec), encoding="utf-8")
    if spec.crm_leads:
        (data_dir / "crm_lead_data.xml").write_text(records.render_crm_lead_xml(spec), encoding="utf-8")
    if spec.purchase_orders:
        (data_dir / "purchase_order_data.xml").write_text(records.render_purchase_order_xml(spec), encoding="utf-8")
    if spec.stock_quants:
        (data_dir / "stock_quant_data.xml").write_text(records.render_stock_quant_xml(spec), encoding="utf-8")
    if spec.manufacturing_orders:
        (data_dir / "mrp_production_data.xml").write_text(records.render_mrp_production_xml(spec), encoding="utf-8")
    if spec.invoices:
        (data_dir / "account_move_data.xml").write_text(records.render_account_move_xml(spec), encoding="utf-8")
    if spec.helpdesk_tickets:
        (data_dir / "helpdesk_ticket_data.xml").write_text(records.render_helpdesk_ticket_xml(spec), encoding="utf-8")
    if spec.quotation_templates:
        (data_dir / "sale_order_template_data.xml").write_text(
            records.render_quotation_template_xml(spec), encoding="utf-8"
        )
    if spec.quotation:
        (data_dir / "sale_order_quotation_data.xml").write_text(
            records.render_sale_order_quotation_xml(spec), encoding="utf-8"
        )
    if spec.example_orders:
        (data_dir / "sale_order_examples_data.xml").write_text(
            records.render_sale_order_examples_xml(spec), encoding="utf-8"
        )
    return module_dir


def zip_module_dir(module_dir: Path, zip_path: Path) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(module_dir.rglob("*")):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(module_dir.parent))
    return zip_path


def build(spec: CustomerSpec, out_dir: Path) -> Path:
    module_dir = write_module_dir(spec, out_dir)
    zip_path = out_dir / f"{spec.module.technical_name}.zip"
    return zip_module_dir(module_dir, zip_path)

"""Baut aus einer CustomerSpec ein installierbares Odoo-Modul: erst als
Verzeichnisbaum, dann als ZIP."""
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
    if spec.partners:
        (data_dir / "res_partner_data.xml").write_text(records.render_res_partner_xml(spec), encoding="utf-8")
    if spec.products:
        (data_dir / "product_data.xml").write_text(records.render_product_xml(spec), encoding="utf-8")
    if spec.boms:
        (data_dir / "mrp_bom_data.xml").write_text(records.render_mrp_bom_xml(spec), encoding="utf-8")
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

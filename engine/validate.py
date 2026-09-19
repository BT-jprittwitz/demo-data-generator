"""Purely static validation of a built Odoo module - without a real Odoo kernel.

Covers the error classes that have actually occurred or been verified so far
(see skills/odoo-demo-data/reference/verified-patterns.md) and generic
structural errors. Does NOT replace a real installation against an Odoo-19.0 kernel -
for that see skills/odoo-demo-data/reference/install-test-protocol.md.
"""
from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .model import SAFE_PURCHASE_ORDER_STATES, SAFE_SALE_ORDER_STATES

# Known Odoo core/enterprise namespaces from which "foreign" xmlids may come.
# Anything else outside the module itself is flagged as a warning,
# because without a running Odoo kernel it cannot be checked whether the reference
# actually exists.
KNOWN_EXTERNAL_PREFIXES = (
    "base.", "uom.", "product.", "mrp.", "sale.", "account.",
    "crm.", "sales_team.", "purchase.", "stock.", "helpdesk.", "utm.",
)

REF_ATTR_RE = re.compile(r"ref\(['\"]([^'\"]+)['\"]\)")


@dataclass
class Finding:
    level: str  # "error" | "warning"
    message: str

    def __str__(self) -> str:
        return f"[{self.level.upper()}] {self.message}"


def validate_module(module_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    manifest_path = module_dir / "__manifest__.py"
    if not manifest_path.exists():
        return [Finding("error", f"__manifest__.py missing in {module_dir}")]

    manifest = _parse_manifest(manifest_path, findings)
    if manifest is None:
        return findings

    data_dir = module_dir / "data"
    declared_files = set(manifest.get("data", []))
    actual_files = {
        f"data/{p.name}" for p in data_dir.glob("*.xml")
    } if data_dir.exists() else set()

    for missing in sorted(declared_files - actual_files):
        findings.append(Finding("error", f"Manifest references {missing}, but the file does not exist."))
    for extra in sorted(actual_files - declared_files):
        findings.append(Finding("error", f"{extra} exists but is not listed in the manifest 'data'."))

    defined_ids: set[str] = set()
    trees: dict[str, ET.Element] = {}
    for xml_path in sorted(data_dir.glob("*.xml")) if data_dir.exists() else []:
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError as e:
            findings.append(Finding("error", f"{xml_path.name}: not well-formed XML ({e})"))
            continue
        trees[xml_path.name] = root
        for rec in root.iter("record"):
            rec_id = rec.get("id")
            if rec_id:
                defined_ids.add(rec_id)

    for fname, root in trees.items():
        _check_records(fname, root, defined_ids, findings)

    barcodes: dict[str, list[str]] = {}
    for fname, root in trees.items():
        for rec in root.iter("record"):
            if rec.get("model") != "product.product":
                continue
            for f in rec.findall("field"):
                if f.get("name") == "barcode" and f.text:
                    barcodes.setdefault(f.text, []).append(rec.get("id", "?"))
    for barcode, ids in barcodes.items():
        if len(ids) > 1:
            findings.append(
                Finding("error", f"Barcode {barcode!r} assigned multiple times: {ids} "
                                  f"(product.product._check_barcode_uniqueness would fail during installation)")
            )

    models_present: set[str] = set()
    has_chart_function = False
    for root in trees.values():
        for rec in root.iter("record"):
            if rec.get("model"):
                models_present.add(rec.get("model"))
        for fn in root.iter("function"):
            if fn.get("model") == "account.chart.template" and fn.get("name") == "try_loading":
                has_chart_function = True

    if "account.move" in models_present and not has_chart_function:
        findings.append(Finding(
            "error",
            "account.move records present, but no account.chart.template.try_loading "
            "<function> - the new company then has no chart of accounts and the move fails "
            "(reference/verified-patterns.md 4.11/4.12)."
        ))
    if "stock.quant" in models_present and "stock.warehouse" not in models_present:
        findings.append(Finding(
            "error",
            "stock.quant records present, but no stock.warehouse for the demo company - "
            "a new company does not get a warehouse automatically "
            "(reference/verified-patterns.md 4.13)."
        ))

    return findings


def _parse_manifest(manifest_path: Path, findings: list[Finding]) -> dict | None:
    try:
        tree = ast.parse(manifest_path.read_text(encoding="utf-8"), filename=str(manifest_path))
    except SyntaxError as e:
        findings.append(Finding("error", f"__manifest__.py: SyntaxError ({e})"))
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            try:
                return ast.literal_eval(node)
            except (ValueError, SyntaxError):
                continue
    findings.append(Finding("error", "__manifest__.py: no dict literal found."))
    return None


def _check_records(fname: str, root: ET.Element, defined_ids: set[str], findings: list[Finding]) -> None:
    for rec in root.iter("record"):
        model = rec.get("model")
        rec_id = rec.get("id", "?")
        context = rec.get("context") or ""

        for f in rec.findall("field"):
            name = f.get("name")

            if model == "product.product" and name == "standard_price":
                if "allowed_company_ids" not in context:
                    findings.append(Finding(
                        "error",
                        f"{fname}: record {rec_id} (product.product) sets standard_price without "
                        f"context=\"{{'allowed_company_ids': [...]}}\" - company_dependent value "
                        f"would be stored against the wrong company "
                        f"(reference/verified-patterns.md 4.7)."
                    ))

            if model == "sale.order" and name == "state" and f.text not in SAFE_SALE_ORDER_STATES:
                findings.append(Finding(
                    "error",
                    f"{fname}: record {rec_id} (sale.order) sets state={f.text!r}, "
                    f"only {sorted(SAFE_SALE_ORDER_STATES)} are verified safe "
                    f"(reference/verified-patterns.md 4.3)."
                ))

            if model == "purchase.order" and name == "state" and f.text not in SAFE_PURCHASE_ORDER_STATES:
                findings.append(Finding(
                    "error",
                    f"{fname}: record {rec_id} (purchase.order) sets state={f.text!r}, "
                    f"only {sorted(SAFE_PURCHASE_ORDER_STATES)} are verified safe "
                    f"(state='purchase' triggers real pickings with purchase_stock, "
                    f"reference/verified-patterns.md 4.10)."
                ))

            if model == "account.move" and name == "state":
                findings.append(Finding(
                    "error",
                    f"{fname}: record {rec_id} (account.move) sets state directly. "
                    f"state='posted' is forbidden in create() (UserError); create as draft "
                    f"and post in the post_init_hook via action_post() "
                    f"(reference/verified-patterns.md 4.12)."
                ))

            if model == "stock.quant" and name in ("inventory_quantity", "inventory_quantity_auto_apply"):
                findings.append(Finding(
                    "error",
                    f"{fname}: record {rec_id} (stock.quant) sets {name!r} - this creates "
                    f"real stock.move/valuation postings. For pure stock display, "
                    f"use quantity (reference/verified-patterns.md 4.13)."
                ))

        if model == "purchase.order":
            field_names = {f.get("name") for f in rec.findall("field")}
            if "picking_type_id" not in field_names:
                findings.append(Finding(
                    "error",
                    f"{fname}: record {rec_id} (purchase.order) does not set picking_type_id - "
                    f"with purchase_stock the column is NOT NULL and the default falls back to the "
                    f"wrong company (reference/verified-patterns.md 4.10)."
                ))

        for f in rec.findall("field"):
            ref = f.get("ref")
            if ref:
                _check_ref(fname, rec_id, ref, defined_ids, findings)
            evl = f.get("eval")
            if evl:
                for ref_match in REF_ATTR_RE.findall(evl):
                    _check_ref(fname, rec_id, ref_match, defined_ids, findings)


def _check_ref(fname: str, rec_id: str, ref: str, defined_ids: set[str], findings: list[Finding]) -> None:
    if "." in ref:
        if not ref.startswith(KNOWN_EXTERNAL_PREFIXES):
            findings.append(Finding(
                "warning",
                f"{fname}: record {rec_id} references {ref!r} - unknown namespace, "
                f"not automatically checkable without a running Odoo kernel. Verify manually."
            ))
        return
    if ref not in defined_ids:
        findings.append(Finding(
            "error",
            f"{fname}: record {rec_id} references {ref!r}, which is not an xml_id defined in the module."
        ))

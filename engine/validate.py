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
    "project.", "maintenance.", "quality.", "quality_control.",
    "sale_subscription.", "industry_fsm.",
)

REF_ATTR_RE = re.compile(r"ref\(['\"]([^'\"]+)['\"]\)")

# base_vat validates res.partner.vat with python-stdnum on create/write (the
# account._check_vat inverse, verified base_vat/models/res_partner.py:104,106-164).
# It is installed transitively via l10n_de, but NOT via l10n_ch - so an invalid
# VAT only aborts the install for localizations that pull base_vat. The static
# check below is therefore only applied when the manifest depends on one of them
# (verified-patterns.md 4.19).
BASE_VAT_LOCALIZATIONS = ("base_vat", "l10n_de")


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

    if set(manifest.get("depends", [])) & set(BASE_VAT_LOCALIZATIONS):
        for fname, root in trees.items():
            _check_partner_vat(fname, root, findings)

    # product.template.recurring_invoice only exists with sale_subscription
    # (verified-patterns 4.25). Setting it without the app aborts the install.
    if "sale_subscription" not in set(manifest.get("depends", [])):
        for fname, root in trees.items():
            for rec in root.iter("record"):
                if rec.get("model") != "product.product":
                    continue
                for f in rec.findall("field"):
                    if f.get("name") == "recurring_invoice":
                        findings.append(Finding(
                            "error",
                            f"{fname}: record {rec.get('id', '?')} (product.product) sets "
                            f"recurring_invoice, but the manifest does not depend on "
                            f"sale_subscription - the field does not exist then "
                            f"(reference/verified-patterns.md 4.25)."
                        ))

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
    if "mrp.production" in models_present and "stock.warehouse" not in models_present:
        findings.append(Finding(
            "error",
            "mrp.production records present, but no stock.warehouse for the demo company - "
            "picking_type_id is required and computed from the company warehouse's "
            "manufacturing operation type (reference/verified-patterns.md 4.17)."
        ))
    if "project.task" in models_present and "project.project" not in models_present:
        findings.append(Finding(
            "error",
            "project.task records present, but no project.project - a task needs a project "
            "(project_id; company_id/stage defaults are derived from it), "
            "reference/verified-patterns.md 4.21."
        ))
    _check_project_task_stages(trees, findings)

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

            if model == "project.task" and name == "state":
                findings.append(Finding(
                    "error",
                    f"{fname}: record {rec_id} (project.task) sets state directly. "
                    f"state is compute+store (from stage_id/dependencies) and must not be "
                    f"set; a new task is '01_in_progress' "
                    f"(reference/verified-patterns.md 4.21)."
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


def _check_project_task_stages(trees: dict[str, ET.Element], findings: list[Finding]) -> None:
    """A project.task's stage must be linked to its project via project.type_ids.

    Verified: ``project.task._compute_stage_id`` resets any stage whose
    ``project_ids`` does not contain the task's project (and ``stage_find`` only
    searches the linked stages), so an unlinked stage silently falls back to the
    project's default stage (verified-patterns.md 4.21)."""
    linked: set[str] = set()
    for root in trees.values():
        for rec in root.iter("record"):
            if rec.get("model") != "project.project":
                continue
            for f in rec.findall("field"):
                if f.get("name") == "type_ids":
                    linked.update(REF_ATTR_RE.findall(f.get("eval") or ""))
    for fname, root in trees.items():
        for rec in root.iter("record"):
            if rec.get("model") != "project.task":
                continue
            for f in rec.findall("field"):
                if f.get("name") == "stage_id" and f.get("ref") and f.get("ref") not in linked:
                    findings.append(Finding(
                        "error",
                        f"{fname}: record {rec.get('id', '?')} (project.task) references "
                        f"stage {f.get('ref')!r}, which is not linked to any project via "
                        f"project.type_ids - _compute_stage_id would reset it "
                        f"(reference/verified-patterns.md 4.21)."
                    ))


def _check_partner_vat(fname: str, root: ET.Element, findings: list[Finding]) -> None:
    """Flag German/Austrian partner VAT numbers with an invalid check digit.

    Only the two checksum algorithms verified against the Odoo 19.0 stdnum
    dependency are implemented (DE = ISO 7064 Mod 11,10, AT = Luhn, see
    verified-patterns.md 4.19); other countries are left to the real install.
    """
    for rec in root.iter("record"):
        if rec.get("model") != "res.partner":
            continue
        vat = ""
        for f in rec.findall("field"):
            if f.get("name") == "vat" and f.text:
                vat = f.text.strip()
        upper = vat.upper()
        if upper.startswith("DE") and not _is_valid_de_vat(vat):
            findings.append(Finding(
                "error",
                f"{fname}: record {rec.get('id', '?')} (res.partner) has VAT {vat!r} with an "
                f"invalid USt-IdNr checksum - base_vat would reject it during installation "
                f"(reference/verified-patterns.md 4.19)."
            ))
        elif upper.startswith("ATU") and not _is_valid_at_uid(vat):
            findings.append(Finding(
                "error",
                f"{fname}: record {rec.get('id', '?')} (res.partner) has VAT {vat!r} with an "
                f"invalid Austrian UID checksum - base_vat would reject it during installation "
                f"(reference/verified-patterns.md 4.19)."
            ))


def _is_valid_de_vat(vat: str) -> bool:
    """German USt-IdNr: 9 digits, ISO 7064 Mod 11,10 (stdnum.de.vat / iso7064.mod_11_10)."""
    number = re.sub(r"[ .\-/,]", "", vat.upper())
    if number.startswith("DE"):
        number = number[2:]
    if len(number) != 9 or not number.isdigit() or number[0] == "0":
        return False
    checksum = 5
    for digit in number:
        checksum = (((checksum or 10) * 2) % 11 + int(digit)) % 10
    return checksum == 1


def _is_valid_at_uid(vat: str) -> bool:
    """Austrian UID: U + 8 digits, last digit = (6 - luhn(number[1:-1])) % 10 (stdnum.at.uid)."""
    number = re.sub(r"[ .\-/]", "", vat.upper())
    if number.startswith("AT"):
        number = number[2:]
    if len(number) != 9 or number[0] != "U" or not number[1:].isdigit():
        return False
    return str((6 - _luhn_checksum(number[1:-1])) % 10) == number[-1]


def _luhn_checksum(number: str) -> int:
    digits = [int(c) for c in reversed(number)]
    total = sum(digits[::2])
    total += sum(sum(divmod(d * 2, 10)) for d in digits[1::2])
    return total % 10

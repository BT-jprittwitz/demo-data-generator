"""Rein statische Validierung eines gebauten Odoo-Moduls - ohne echten Odoo-
Kernel (kein Docker auf dieser Maschine verfuegbar, siehe HANDOVER.md).

Deckt genau die bisher real aufgetretenen bzw. verifizierten Fehlerklassen ab
(HANDOVER.md 4.1, 4.3, 4.7) und generische Strukturfehler. Ersetzt KEINE echte
Installation gegen eine Odoo-19.0-Instanz - das bleibt der naechste Ausbauschritt
(docker/, siehe dortige README) bzw. bis dahin ein manueller Test durch den
Nutzer mit vollstaendigem Traceback bei Fehlern (harte Arbeitsregel, Abschnitt 3).
"""
from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .model import SAFE_SALE_ORDER_STATES

# Bekannte Odoo-Core-Namespaces, aus denen "fremde" xmlids stammen duerfen.
# Alles andere ausserhalb des eigenen Moduls wird als Warnung markiert, weil
# ohne laufenden Odoo-Kernel nicht geprueft werden kann, ob die Referenz
# tatsaechlich existiert.
KNOWN_EXTERNAL_PREFIXES = ("base.", "uom.", "product.", "mrp.", "sale.", "account.")

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
        return [Finding("error", f"__manifest__.py fehlt in {module_dir}")]

    manifest = _parse_manifest(manifest_path, findings)
    if manifest is None:
        return findings

    data_dir = module_dir / "data"
    declared_files = set(manifest.get("data", []))
    actual_files = {
        f"data/{p.name}" for p in data_dir.glob("*.xml")
    } if data_dir.exists() else set()

    for missing in sorted(declared_files - actual_files):
        findings.append(Finding("error", f"Manifest verweist auf {missing}, Datei existiert nicht."))
    for extra in sorted(actual_files - declared_files):
        findings.append(Finding("error", f"{extra} existiert, ist aber nicht im Manifest 'data' gelistet."))

    defined_ids: set[str] = set()
    trees: dict[str, ET.Element] = {}
    for xml_path in sorted(data_dir.glob("*.xml")) if data_dir.exists() else []:
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError as e:
            findings.append(Finding("error", f"{xml_path.name}: nicht wohlgeformtes XML ({e})"))
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
                Finding("error", f"Barcode {barcode!r} mehrfach vergeben: {ids} "
                                  f"(product.product._check_barcode_uniqueness wuerde bei der Installation fehlschlagen)")
            )

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
    findings.append(Finding("error", "__manifest__.py: kein Dict-Literal gefunden."))
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
                        f"{fname}: record {rec_id} (product.product) setzt standard_price ohne "
                        f"context=\"{{'allowed_company_ids': [...]}}\" - company_dependent-Wert "
                        f"wuerde gegen die falsche Company gespeichert (HANDOVER.md 4.7)."
                    ))

            if model == "sale.order" and name == "state" and f.text not in SAFE_SALE_ORDER_STATES:
                findings.append(Finding(
                    "error",
                    f"{fname}: record {rec_id} (sale.order) setzt state={f.text!r}, "
                    f"nur {sorted(SAFE_SALE_ORDER_STATES)} sind verifiziert sicher (HANDOVER.md 4.3)."
                ))

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
                f"{fname}: record {rec_id} referenziert {ref!r} - unbekannter Namespace, "
                f"nicht automatisch pruefbar ohne laufenden Odoo-Kernel. Manuell verifizieren."
            ))
        return
    if ref not in defined_ids:
        findings.append(Finding(
            "error",
            f"{fname}: record {rec_id} referenziert {ref!r}, das ist keine im Modul definierte xml_id."
        ))

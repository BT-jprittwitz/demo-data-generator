"""Laedt eine Kunden-Spezifikation aus einem JSON-Dict in die Dataclasses aus model.py.

Bewusst kein generisches/"magisches" Mapping (z.B. **kwargs direkt in die Dataclass) -
jedes Feld wird explizit gelesen, damit ein Tippfehler im JSON eine klare Fehlermeldung
statt eines TypeError aus dem Dataclass-Konstruktor ergibt.
"""
from __future__ import annotations

from typing import Any

from .model import (
    Bom,
    BomLine,
    Company,
    CustomerSpec,
    Module,
    Partner,
    Product,
    SaleOrder,
    SaleOrderLine,
    SpecError,
)


def _get(d: dict[str, Any], key: str, where: str, default=..., required=False):
    if key in d:
        return d[key]
    if required:
        raise SpecError(f"{where}: Pflichtfeld {key!r} fehlt.")
    if default is ...:
        return None
    return default


def load_module(d: dict[str, Any]) -> Module:
    return Module(
        technical_name=_get(d, "technical_name", "module", required=True),
        title=_get(d, "title", "module", required=True),
        summary=_get(d, "summary", "module", required=True),
        description=_get(d, "description", "module", default=""),
        category=_get(d, "category", "module", default="Sales"),
    )


def load_company(d: dict[str, Any]) -> Company:
    return Company(
        xml_id=_get(d, "xml_id", "company", default="demo_company"),
        name=_get(d, "name", "company", required=True),
        street=_get(d, "street", "company", required=True),
        city=_get(d, "city", "company", required=True),
        zip=_get(d, "zip", "company", required=True),
        country_xmlid=_get(d, "country_xmlid", "company", required=True),
        vat=_get(d, "vat", "company", default=None),
        currency_xmlid=_get(d, "currency_xmlid", "company", default=None),
    )


def load_partner(d: dict[str, Any]) -> Partner:
    xml_id = _get(d, "xml_id", "partner", required=True)
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
    )


def load_bom(d: dict[str, Any]) -> Bom:
    xml_id = _get(d, "xml_id", "bom", required=True)
    where = f"bom {xml_id}"
    lines_raw = _get(d, "lines", where, required=True)
    lines = [
        BomLine(
            product_xmlid=_get(ld, "product_xmlid", f"{where} line", required=True),
            qty=_get(ld, "qty", f"{where} line", required=True),
            uom_xmlid=_get(ld, "uom_xmlid", f"{where} line", default="uom.product_uom_unit"),
        )
        for ld in lines_raw
    ]
    return Bom(
        xml_id=xml_id,
        product_xmlid=_get(d, "product_xmlid", where, required=True),
        lines=lines,
        qty=_get(d, "qty", where, default=1.0),
        uom_xmlid=_get(d, "uom_xmlid", where, default="uom.product_uom_unit"),
    )


def load_sale_order(d: dict[str, Any]) -> SaleOrder:
    xml_id = _get(d, "xml_id", "sale_order", required=True)
    where = f"sale_order {xml_id}"
    lines_raw = _get(d, "lines", where, required=True)
    lines = [
        SaleOrderLine(
            product_xmlid=_get(ld, "product_xmlid", f"{where} line", required=True),
            qty=_get(ld, "qty", f"{where} line", required=True),
            description=_get(ld, "description", f"{where} line", required=True),
        )
        for ld in lines_raw
    ]
    return SaleOrder(
        xml_id=xml_id,
        partner_xmlid=_get(d, "partner_xmlid", where, required=True),
        lines=lines,
        state=_get(d, "state", where, default="sent"),
        date_order=_get(d, "date_order", where, default=None),
    )


def load_spec(d: dict[str, Any]) -> CustomerSpec:
    if "module" not in d:
        raise SpecError("Spezifikation: Pflichtfeld 'module' fehlt.")
    if "company" not in d:
        raise SpecError("Spezifikation: Pflichtfeld 'company' fehlt.")
    quotation_raw = d.get("quotation")
    return CustomerSpec(
        module=load_module(d["module"]),
        company=load_company(d["company"]),
        partners=[load_partner(p) for p in d.get("partners", [])],
        products=[load_product(p) for p in d.get("products", [])],
        boms=[load_bom(b) for b in d.get("boms", [])],
        quotation=load_sale_order(quotation_raw) if quotation_raw else None,
        example_orders=[load_sale_order(o) for o in d.get("example_orders", [])],
    )

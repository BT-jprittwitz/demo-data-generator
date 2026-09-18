"""Datenmodell fuer eine Kunden-Demo-Daten-Spezifikation.

Deckt ausschliesslich die in HANDOVER.md Abschnitt 4 verifizierten Odoo-19.0-
Objektarten ab: res.company, res.partner, product.product, mrp.bom, sale.order.
Bewusst KEINE weiteren Objektarten (siehe "bedarfsgetriebenes Wachstum" in
HANDOVER.md) - neue Archetypen brauchen zuerst eine eigene Verifikation gegen
den Odoo-Source, bevor hier ein Baustein dafuer entsteht.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# sale.order: nur diese States sind gegen sale_stock-Beschaffungslogik
# (HANDOVER.md 4.3) sicher, weil eine frische Demo-Company kein Warehouse/
# keine Routen konfiguriert hat.
SAFE_SALE_ORDER_STATES = {"draft", "sent"}

# product.product.type: nur diese zwei Werte kommen in den verifizierten
# Mustern vor (siehe HANDOVER.md 4.1 / 5).
VALID_PRODUCT_TYPES = {"consu", "service"}


class SpecError(ValueError):
    """Ungueltige oder unvollstaendige Kunden-Spezifikation."""


@dataclass
class Company:
    name: str
    street: str
    city: str
    zip: str
    country_xmlid: str
    xml_id: str = "demo_company"
    vat: str | None = None
    currency_xmlid: str | None = None


@dataclass
class Partner:
    xml_id: str
    name: str
    country_xmlid: str
    street: str
    city: str
    zip: str
    vat: str | None = None
    is_company: bool = True
    supplier_rank: int = 0
    customer_rank: int = 1


@dataclass
class Product:
    xml_id: str
    name: str
    type: str
    sale_ok: bool
    purchase_ok: bool
    list_price: float = 0.0
    # Cost/Einstandspreis. product.product.standard_price ist company_dependent
    # (verifiziert, siehe HANDOVER.md 4.7) - der Builder wrapped den record
    # deshalb automatisch mit context="{'allowed_company_ids': [...]}" sobald
    # dieser Wert != None ist.
    standard_price: float | None = None
    # None = nicht explizit gesetzt -> wird in __post_init__ aus type abgeleitet
    # (verifiziert gegen addons/stock/models/product.py compute_is_storable():
    # ein 'service'-Produkt ist nie lagerbar, is_storable=True waere dort falsch).
    is_storable: bool | None = None
    default_code: str | None = None
    barcode: str | None = None
    weight: float | None = None
    volume: float | None = None
    description_sale: str | None = None

    def __post_init__(self) -> None:
        if self.type not in VALID_PRODUCT_TYPES:
            raise SpecError(
                f"Product {self.xml_id!r}: type={self.type!r} ist nicht verifiziert "
                f"(erlaubt: {sorted(VALID_PRODUCT_TYPES)}). Vor Verwendung eines neuen "
                f"Werts gegen odoo/addons/product/models/product_template.py pruefen."
            )
        if self.is_storable is None:
            self.is_storable = self.type == "consu"


@dataclass
class BomLine:
    product_xmlid: str
    qty: float
    uom_xmlid: str = "uom.product_uom_unit"


@dataclass
class Bom:
    xml_id: str
    product_xmlid: str
    lines: list[BomLine]
    qty: float = 1.0
    uom_xmlid: str = "uom.product_uom_unit"


@dataclass
class SaleOrderLine:
    product_xmlid: str
    qty: float
    description: str


@dataclass
class SaleOrder:
    xml_id: str
    partner_xmlid: str
    lines: list[SaleOrderLine]
    state: str = "sent"
    date_order: str | None = None

    def __post_init__(self) -> None:
        if self.state not in SAFE_SALE_ORDER_STATES:
            raise SpecError(
                f"SaleOrder {self.xml_id!r}: state={self.state!r} ist nicht in den "
                f"verifiziert sicheren Werten {sorted(SAFE_SALE_ORDER_STATES)} "
                f"(siehe HANDOVER.md 4.3 - state='sale' loest echte Beschaffungslogik "
                f"aus und schlaegt fehl, weil die Demo-Company kein Warehouse hat)."
            )


@dataclass
class Module:
    technical_name: str
    title: str
    summary: str
    description: str
    category: str = "Sales"


@dataclass
class CustomerSpec:
    module: Module
    company: Company
    partners: list[Partner] = field(default_factory=list)
    products: list[Product] = field(default_factory=list)
    boms: list[Bom] = field(default_factory=list)
    quotation: SaleOrder | None = None
    example_orders: list[SaleOrder] = field(default_factory=list)

    def __post_init__(self) -> None:
        barcodes = [p.barcode for p in self.products if p.barcode]
        dupes = {b for b in barcodes if barcodes.count(b) > 1}
        if dupes:
            raise SpecError(
                f"Doppelte Barcodes in der Spezifikation: {sorted(dupes)} "
                f"(product.product._check_barcode_uniqueness wuerde die Installation "
                f"mit ValidationError abbrechen)."
            )
        product_ids = {p.xml_id for p in self.products}
        partner_ids = {p.xml_id for p in self.partners}
        for bom in self.boms:
            _require(bom.product_xmlid, product_ids, f"Bom {bom.xml_id}: product_xmlid")
            for line in bom.lines:
                _require(line.product_xmlid, product_ids, f"Bom {bom.xml_id}: bom_line product_xmlid")
        for order in ([self.quotation] if self.quotation else []) + self.example_orders:
            _require(order.partner_xmlid, partner_ids, f"SaleOrder {order.xml_id}: partner_xmlid")
            for line in order.lines:
                _require(line.product_xmlid, product_ids, f"SaleOrder {order.xml_id}: order_line product_xmlid")

    @property
    def needs_mrp(self) -> bool:
        return bool(self.boms)


def _require(xmlid: str, known: set[str], where: str) -> None:
    if xmlid not in known:
        raise SpecError(
            f"{where} referenziert {xmlid!r}, das ist keine in dieser Spezifikation "
            f"definierte xml_id. Tippfehler oder fehlender Record?"
        )

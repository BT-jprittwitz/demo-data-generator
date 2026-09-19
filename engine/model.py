"""Data model for a customer demo data specification.

Covers exclusively the Odoo-19.0 object types verified in verified-patterns.md
section 4: res.company, res.partner, product.product, mrp.bom, sale.order.
Deliberately NO further object types (see "demand-driven growth" in
verified-patterns.md) - new archetypes first need their own verification against
the Odoo source before a building block for them is created here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# sale.order: only these states are safe against sale_stock procurement logic
# (verified-patterns.md 4.3), because a fresh demo company has no warehouse/
# no routes configured.
SAFE_SALE_ORDER_STATES = {"draft", "sent"}

# product.product.type: only these two values appear in the verified
# patterns (see verified-patterns.md 4.1 / 5).
VALID_PRODUCT_TYPES = {"consu", "service"}

# crm.lead.type: verified against addons/crm/models/crm_lead.py (Selection).
VALID_CRM_LEAD_TYPES = {"lead", "opportunity"}

# purchase.order.state: only these values are uncritical at creation time. With
# purchase_stock installed (auto_install), state='purchase' creates real
# stock.picking/stock.move during line create (verified against
# purchase_stock/models/purchase_order_line.py create()); therefore deliberately
# excluded (see verified-patterns.md 4.10).
SAFE_PURCHASE_ORDER_STATES = {"draft", "sent"}

# account.move.move_type: verified against addons/account/models/account_move.py.
# state='posted' must NOT be set in create() (UserError, verified
# account_move.py create()); the invoices are created as draft and posted in the
# post_init_hook via action_post() (see verified-patterns.md 4.12).
VALID_INVOICE_MOVE_TYPES = {"out_invoice", "in_invoice"}

# Default demo-data language per country. Key is the lower-case ISO code taken
# from the country xmlid suffix (e.g. "base.ch" -> "ch"). This is a primary
# language per country; the spec's optional "language" field overrides it.
# Language codes must exist in res.lang (verified: base/data/res.lang.csv).
DEFAULT_LANGUAGE = "en_US"
COUNTRY_DEFAULT_LANGUAGE = {
    "ch": "de_CH",
    "de": "de_DE",
    "at": "de_DE",
    "fr": "fr_FR",
    "it": "it_IT",
    "nl": "nl_NL",
    "be": "nl_BE",
    "es": "es_ES",
    "pt": "pt_PT",
    "us": "en_US",
    "gb": "en_GB",
    "br": "pt_BR",
}

# Automatically generated team names per language prefix. A spec may override
# them explicitly via "crm_team_name" / "helpdesk_team_name".
_TEAM_NAMES = {
    "de": ("Vertrieb", "Kundendienst"),
    "en": ("Sales", "Customer Service"),
    "fr": ("Ventes", "Service client"),
    "it": ("Vendite", "Servizio clienti"),
}


def country_code(country_xmlid: str) -> str:
    return (country_xmlid or "").rsplit(".", 1)[-1].lower()


def derive_language(country_xmlid: str) -> str:
    return COUNTRY_DEFAULT_LANGUAGE.get(country_code(country_xmlid), DEFAULT_LANGUAGE)


def default_team_names(language: str) -> tuple[str, str]:
    prefix = (language or DEFAULT_LANGUAGE).split("_")[0]
    return _TEAM_NAMES.get(prefix, _TEAM_NAMES["en"])


class SpecError(ValueError):
    """Invalid or incomplete customer specification."""


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
    # Chart of accounts code (e.g. "ch" for l10n_ch). If set, the module
    # loads the chart of accounts via <function model="account.chart.template" name="try_loading">
    # directly after company creation (verified pattern from
    # account/demo/account_demo.xml, see verified-patterns.md 4.11). A company newly
    # created via XML does NOT get a chart of accounts automatically (account.load
    # only runs if the company has a parent with chart_template, and then
    # delayed in precommit) - therefore explicit.
    chart_template: str | None = None


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
    # Cost/purchase price. product.product.standard_price is company_dependent
    # (verified, see verified-patterns.md 4.7) - the builder therefore wraps the record
    # automatically with context="{'allowed_company_ids': [...]}" as soon as
    # this value != None.
    standard_price: float | None = None
    # None = not explicitly set -> derived from type in __post_init__
    # (verified against addons/stock/models/product.py compute_is_storable():
    # a 'service' product is never storable, is_storable=True would be wrong there).
    is_storable: bool | None = None
    default_code: str | None = None
    barcode: str | None = None
    weight: float | None = None
    volume: float | None = None
    description_sale: str | None = None

    def __post_init__(self) -> None:
        if self.type not in VALID_PRODUCT_TYPES:
            raise SpecError(
                f"Product {self.xml_id!r}: type={self.type!r} is not verified "
                f"(allowed: {sorted(VALID_PRODUCT_TYPES)}). Before using a new "
                f"value, check against odoo/addons/product/models/product_template.py."
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
class ManufacturingOrder:
    """``mrp.production`` as a DRAFT manufacturing order.

    Verified against odoo/odoo@19.0 (addons/mrp/models/mrp_production.py):
    - required for create(): ``product_id``, ``product_qty`` (SQL Constraint
      ``check (product_qty > 0)``), ``product_uom_id``, ``picking_type_id``,
      ``location_src_id``, ``location_dest_id``, ``date_start``. The last four
      are computed from the company's warehouse manufacturing operation type
      (``stock.warehouse.manu_type_id``, added by mrp) - so a company warehouse
      MUST exist (``_compute_picking_type_id`` -> ``_warehouse_redirect_warning``
      otherwise). This is why manufacturing implies inventory (verified-patterns
      "manufacturing needs a warehouse").
    - ``state`` is compute+store+readonly -> never set it; a new MO is ``draft``.
    - ``create()`` only generates draft ``stock.move``/``mrp.workorder`` records
      (and a production group); it does NOT call ``action_confirm``, so no stock
      is posted.
    """

    xml_id: str
    product_xmlid: str
    qty: float
    bom_xmlid: str | None = None
    date_start: str | None = None

    def __post_init__(self) -> None:
        if self.qty <= 0:
            raise SpecError(
                f"ManufacturingOrder {self.xml_id!r}: qty={self.qty} must be > 0 "
                f"(SQL Constraint _qty_positive: check (product_qty > 0))."
            )


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
                f"SaleOrder {self.xml_id!r}: state={self.state!r} is not among the "
                f"verified safe values {sorted(SAFE_SALE_ORDER_STATES)} "
                f"(see verified-patterns.md 4.3 - state='sale' triggers real procurement logic "
                f"and fails because the demo company has no warehouse)."
            )


@dataclass
class CrmLead:
    """crm.lead (Community module crm). Verified: only name and type are
    required; stage_id/team_id/company_id are compute+store+readonly=False and
    can be set. The default stages crm.stage_lead1..lead4 exist
    after installation (crm/data/crm_stage_data.xml)."""

    xml_id: str
    name: str
    type: str = "opportunity"
    partner_xmlid: str | None = None
    contact_name: str | None = None
    email_from: str | None = None
    phone: str | None = None
    expected_revenue: float | None = None
    probability: float | None = None
    stage_xmlid: str = "crm.stage_lead1"
    description: str | None = None
    priority: str | None = None

    def __post_init__(self) -> None:
        if self.type not in VALID_CRM_LEAD_TYPES:
            raise SpecError(
                f"CrmLead {self.xml_id!r}: type={self.type!r} invalid "
                f"(allowed: {sorted(VALID_CRM_LEAD_TYPES)}, see crm/models/crm_lead.py)."
            )
        if self.probability is not None and not 0 <= self.probability <= 100:
            raise SpecError(
                f"CrmLead {self.xml_id!r}: probability must be between 0 and 100 "
                f"(SQL constraint _check_probability in crm/models/crm_lead.py)."
            )


@dataclass
class PurchaseOrderLine:
    product_xmlid: str
    qty: float
    price_unit: float
    description: str
    date_planned: str | None = None


@dataclass
class PurchaseOrder:
    """purchase.order. State deliberately limited to draft/sent: with
    purchase_stock (auto_install as soon as purchase+stock are installed),
    state='purchase' creates real pickings (verified-patterns.md 4.10). name/date_order are
    filled via default/sequence; product_uom_id is named that way in 19.0 (not
    product_uom); the tax field is called tax_ids (not taxes_id)."""

    xml_id: str
    partner_xmlid: str
    lines: list[PurchaseOrderLine]
    state: str = "draft"
    date_order: str | None = None
    partner_ref: str | None = None

    def __post_init__(self) -> None:
        if self.state not in SAFE_PURCHASE_ORDER_STATES:
            raise SpecError(
                f"PurchaseOrder {self.xml_id!r}: state={self.state!r} is not in "
                f"{sorted(SAFE_PURCHASE_ORDER_STATES)}. state='purchase' triggers real "
                f"stock postings with purchase_stock (verified-patterns.md 4.10)."
            )


@dataclass
class Warehouse:
    xml_id: str = "warehouse_demo"
    code: str = "DEMO"


@dataclass
class StockQuant:
    """stock.quant. Deliberately WITHOUT setting inventory_quantity (only quantity): then
    the else branch super().create() runs in the create() override and NO
    stock.move / no valuation posting is created (verified, verified-patterns.md 4.13).
    location_id is resolved in the builder to the demo warehouse's lot_stock_id."""

    product_xmlid: str
    qty: float


@dataclass
class InvoiceLine:
    product_xmlid: str
    qty: float
    price_unit: float
    description: str


@dataclass
class Invoice:
    xml_id: str
    move_type: str
    partner_xmlid: str
    invoice_date: str
    lines: list[InvoiceLine]
    ref: str | None = None

    def __post_init__(self) -> None:
        if self.move_type not in VALID_INVOICE_MOVE_TYPES:
            raise SpecError(
                f"Invoice {self.xml_id!r}: move_type={self.move_type!r} invalid "
                f"(allowed: {sorted(VALID_INVOICE_MOVE_TYPES)}, see "
                f"account/models/account_move.py)."
            )


@dataclass
class HelpdeskTicket:
    """helpdesk.ticket (Enterprise). Verified: only name (and kanban_state with
    default) are required; team_id has default _default_team_id. Tickets are
    keyed in the builder to the helpdesk.team automatically created per company
    for the demo company (helpdesk/models/res_company.py create() creates a team
    per company), so that company_id (related team_id.company_id) matches and
    the constraint _check_partner_id_has_the_same_company does not fail."""

    xml_id: str
    name: str
    partner_xmlid: str | None = None
    stage_xmlid: str = "helpdesk.stage_new"
    priority: str | None = None
    description: str | None = None


@dataclass
class Module:
    technical_name: str
    title: str
    summary: str
    description: str = ""
    category: str = "Sales"


@dataclass
class CustomerSpec:
    module: Module
    company: Company
    partners: list[Partner] = field(default_factory=list)
    products: list[Product] = field(default_factory=list)
    boms: list[Bom] = field(default_factory=list)
    manufacturing_orders: list[ManufacturingOrder] = field(default_factory=list)
    quotation: SaleOrder | None = None
    example_orders: list[SaleOrder] = field(default_factory=list)
    crm_leads: list[CrmLead] = field(default_factory=list)
    purchase_orders: list[PurchaseOrder] = field(default_factory=list)
    stock_quants: list[StockQuant] = field(default_factory=list)
    invoices: list[Invoice] = field(default_factory=list)
    helpdesk_tickets: list[HelpdeskTicket] = field(default_factory=list)
    # Demo-data language. None -> derived from the company country (see
    # derive_language). Overridable per spec (e.g. an English-only IT lead).
    language: str | None = None
    # Team names for the auto-created teams. None -> language-dependent default
    # (see default_team_names), overridable per spec.
    crm_team_name: str | None = None
    helpdesk_team_name: str | None = None
    # "full" -> account_accountant (Enterprise, full accounting including
    #           account_reports/bank reconciliation). "invoicing" -> only account
    #           (Community-compatible, the app is then called "Invoicing").
    # Background: the `account` module alone installs only Invoicing;
    # account_accountant is auto_install=True, but only together with
    # mail_enterprise - so not automatically in a fresh DB (see
    # verified-patterns.md 4.15).
    accounting_app: str = "full"

    def __post_init__(self) -> None:
        if self.accounting_app not in {"full", "invoicing"}:
            raise SpecError(
                f"accounting_app={self.accounting_app!r} invalid "
                f"(allowed: 'full' = account_accountant, 'invoicing' = account)."
            )
        barcodes = [p.barcode for p in self.products if p.barcode]
        dupes = {b for b in barcodes if barcodes.count(b) > 1}
        if dupes:
            raise SpecError(
                f"Duplicate barcodes in the specification: {sorted(dupes)} "
                f"(product.product._check_barcode_uniqueness would abort the installation "
                f"with ValidationError)."
            )
        product_ids = {p.xml_id for p in self.products}
        partner_ids = {p.xml_id for p in self.partners}
        bom_ids = {b.xml_id for b in self.boms}
        if self.manufacturing_orders and not self.boms:
            raise SpecError(
                "manufacturing_orders present but no boms: a manufacturing order needs a "
                "bill of materials for its product (mrp.production.bom_id / components)."
            )
        for bom in self.boms:
            _require(bom.product_xmlid, product_ids, f"Bom {bom.xml_id}: product_xmlid")
            for line in bom.lines:
                _require(line.product_xmlid, product_ids, f"Bom {bom.xml_id}: bom_line product_xmlid")
        for mo in self.manufacturing_orders:
            _require(mo.product_xmlid, product_ids, f"ManufacturingOrder {mo.xml_id}: product_xmlid")
            if mo.bom_xmlid:
                _require(mo.bom_xmlid, bom_ids, f"ManufacturingOrder {mo.xml_id}: bom_xmlid")
        for order in ([self.quotation] if self.quotation else []) + self.example_orders:
            _require(order.partner_xmlid, partner_ids, f"SaleOrder {order.xml_id}: partner_xmlid")
            for line in order.lines:
                _require(line.product_xmlid, product_ids, f"SaleOrder {order.xml_id}: order_line product_xmlid")
        for lead in self.crm_leads:
            if lead.partner_xmlid:
                _require(lead.partner_xmlid, partner_ids, f"CrmLead {lead.xml_id}: partner_xmlid")
        for po in self.purchase_orders:
            _require(po.partner_xmlid, partner_ids, f"PurchaseOrder {po.xml_id}: partner_xmlid")
            for line in po.lines:
                _require(line.product_xmlid, product_ids, f"PurchaseOrder {po.xml_id}: order_line product_xmlid")
        for quant in self.stock_quants:
            _require(quant.product_xmlid, product_ids, f"StockQuant {quant.product_xmlid!r}: product_xmlid")
        for invoice in self.invoices:
            _require(invoice.partner_xmlid, partner_ids, f"Invoice {invoice.xml_id}: partner_xmlid")
            for line in invoice.lines:
                _require(line.product_xmlid, product_ids, f"Invoice {invoice.xml_id}: invoice_line product_xmlid")
        for ticket in self.helpdesk_tickets:
            if ticket.partner_xmlid:
                _require(ticket.partner_xmlid, partner_ids, f"HelpdeskTicket {ticket.xml_id}: partner_xmlid")

    @property
    def needs_mrp(self) -> bool:
        return bool(self.boms) or bool(self.manufacturing_orders)

    @property
    def needs_crm(self) -> bool:
        return bool(self.crm_leads)

    @property
    def needs_purchase(self) -> bool:
        return bool(self.purchase_orders)

    @property
    def needs_stock(self) -> bool:
        return bool(self.stock_quants)

    @property
    def needs_warehouse(self) -> bool:
        # Purchasing needs a warehouse (purchase_stock: picking_type_id required,
        # default from the company warehouse, otherwise NotNullViolation - actually
        # occurred, see verified-patterns.md 4.10). Stock likewise. Manufacturing
        # needs it too (mrp.production.picking_type_id <- warehouse.manu_type_id);
        # the dependency is one-sided: warehouse never implies manufacturing.
        return self.needs_purchase or self.needs_stock or self.needs_mrp

    @property
    def needs_account(self) -> bool:
        return bool(self.invoices) or bool(self.company.chart_template)

    @property
    def needs_helpdesk(self) -> bool:
        return bool(self.helpdesk_tickets)

    @property
    def resolved_language(self) -> str:
        """Demo-data language: explicit spec value, else derived from the
        company country."""
        return self.language or derive_language(self.company.country_xmlid)

    @property
    def resolved_crm_team_name(self) -> str:
        if self.crm_team_name:
            return self.crm_team_name
        return default_team_names(self.resolved_language)[0]

    @property
    def resolved_helpdesk_team_name(self) -> str:
        if self.helpdesk_team_name:
            return self.helpdesk_team_name
        return default_team_names(self.resolved_language)[1]


def _require(xmlid: str, known: set[str], where: str) -> None:
    if xmlid not in known:
        raise SpecError(
            f"{where} references {xmlid!r}, which is not an xml_id defined in this "
            f"specification. Typo or missing record?"
        )

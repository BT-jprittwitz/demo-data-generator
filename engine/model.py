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

# project.task.priority: verified against addons/project/models/project_task.py
# (Selection: '0' Low, '1' Medium, '2' High, '3' Urgent).
VALID_TASK_PRIORITIES = {"0", "1", "2", "3"}

# project.project.privacy_visibility: verified against
# addons/project/models/project_project.py (Selection, required, default 'portal').
VALID_PROJECT_PRIVACY = {"followers", "invited_users", "employees", "portal"}

# maintenance.request.maintenance_type: verified against
# addons/maintenance/models/maintenance.py (Selection: corrective/preventive).
VALID_MAINTENANCE_TYPES = {"corrective", "preventive"}

# quality.check.quality_state: verified against
# enterprise/quality/models/quality.py (Selection: none/pass/fail).
VALID_QUALITY_STATES = {"none", "pass", "fail"}

# quality.point.test_type / quality.check.test_type_id: a m2o to
# quality.point.test_type, addressed by its `technical_name`. The two values
# shipped with the Quality app (quality_control) are verified (verified-patterns
# 4.24).
VALID_QUALITY_TEST_TYPES = {"passfail", "measure"}

# quality.point.measure_on / quality.check.measure_on: 'move_line' is forbidden
# with an mrp_operation picking type (quality_mrp raises a UserError), so only
# these two are allowed for manufacturing quality (verified-patterns 4.24).
VALID_QUALITY_MEASURE_ON = {"product", "operation"}

# subscription plan shorthand -> shipped sale.subscription.plan xmlid
# (sale_subscription/data/sale_subscription_data.xml, noupdate). Verified: only
# these two plans ship as data (verified-patterns 4.25).
VALID_SUBSCRIPTION_PLANS = {"month", "year"}

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
# Tuple order: (crm, helpdesk, maintenance).
_TEAM_NAMES = {
    "de": ("Vertrieb", "Kundendienst", "Instandhaltung"),
    "en": ("Sales", "Customer Service", "Maintenance"),
    "fr": ("Ventes", "Service client", "Maintenance"),
    "it": ("Vendite", "Servizio clienti", "Manutenzione"),
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
    # product.template.recurring_invoice: only exists with `sale_subscription`
    # (verified-patterns 4.25). None = do not touch the field (so modules without
    # the Subscriptions app install fine); validate.py flags a set value when the
    # manifest does not depend on sale_subscription.
    recurring_invoice: bool | None = None

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
class QuotationTemplateLine:
    """``sale.order.template.line`` (module ``sale_management``).

    Verified against addons/sale_management/models/sale_order_template_line.py:
    a line without ``display_type`` must carry ``product_id`` AND
    ``product_uom_id`` (SQL Constraint ``_accountable_product_id_required``);
    ``product_uom_qty`` is required; ``name`` is the (translatable) description.
    ``product_uom_id`` is normally computed from the product but is set
    explicitly so the CHECK constraint can never race the compute.
    """

    product_xmlid: str
    qty: float = 1.0
    description: str | None = None


@dataclass
class QuotationTemplate:
    """``sale.order.template`` = "Angebotsvorlage" (module ``sale_management``).

    Verified against addons/sale_management/models/sale_order_template.py:
    only ``name`` is required; ``company_id`` defaults to ``env.company``;
    ``note`` (Terms and conditions) is Html/translatable; ``number_of_days`` is
    the quotation validity. ``require_signature``/``require_payment`` are
    computed from the company and are therefore not set.
    """

    xml_id: str
    name: str
    lines: list[QuotationTemplateLine]
    note: str | None = None
    number_of_days: int | None = None
    sequence: int = 10


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
class ProjectTaskStage:
    """``project.task.type`` = the task stages (Kanban columns) of a project.

    Verified against addons/project/models/project_task.py: a task's ``stage_id``
    is only valid for a project the stage is linked to (``project_ids`` /
    ``project.type_ids``); ``stage_find``/``_compute_stage_id`` otherwise override
    it. The builder therefore links every defined task stage to every project.
    ``project.task.type`` has NO default records in 19.0 - the stages must be
    created (unlike ``project.project.stage``, which ships as
    ``project.project_project_stage_0..3``).
    """

    xml_id: str
    name: str
    sequence: int = 10
    fold: bool = False


@dataclass
class Project:
    """``project.project``. Verified against
    addons/project/models/project_project.py: only ``name`` is required;
    ``company_id`` is compute+store+readonly=False; ``stage_id`` references the
    core ``project.project.stage`` records (``project.project_project_stage_*``);
    ``privacy_visibility`` is required with default 'portal'. ``partner_id`` must
    belong to the same company as the project (``_inverse_company_id``).
    ``type_ids`` carries the project's task stages (linked by the builder)."""

    xml_id: str
    name: str
    stage_xmlid: str | None = None
    partner_xmlid: str | None = None
    description: str | None = None
    date_start: str | None = None
    date_end: str | None = None
    privacy_visibility: str | None = None
    # project.project.is_fsm (added by `industry_fsm`, Enterprise): marks the
    # project as a Field Service project. Verified: a FSM project requires a
    # company_id (DB CHECK _company_id_required_for_fsm_project) and its task
    # stages are auto-assigned by industry_fsm's create() override, so the
    # renderer omits type_ids for FSM projects (verified-patterns 4.26).
    is_fsm: bool = False

    def __post_init__(self) -> None:
        if self.privacy_visibility is not None and self.privacy_visibility not in VALID_PROJECT_PRIVACY:
            raise SpecError(
                f"Project {self.xml_id!r}: privacy_visibility={self.privacy_visibility!r} "
                f"invalid (allowed: {sorted(VALID_PROJECT_PRIVACY)}, see "
                f"addons/project/models/project_project.py)."
            )


@dataclass
class ProjectTask:
    """``project.task``. Verified against
    addons/project/models/project_task.py: only ``name`` is required;
    ``project_id``/``stage_id``/``company_id`` are compute+store+readonly=False and
    may be set. ``stage_id`` must be a stage linked to the task's project
    (otherwise ``_compute_stage_id`` resets it). ``state`` is computed+store and
    must NOT be set."""

    xml_id: str
    name: str
    project_xmlid: str
    stage_xmlid: str | None = None
    partner_xmlid: str | None = None
    description: str | None = None
    priority: str | None = None
    date_deadline: str | None = None
    allocated_hours: float | None = None

    def __post_init__(self) -> None:
        if self.priority is not None and self.priority not in VALID_TASK_PRIORITIES:
            raise SpecError(
                f"ProjectTask {self.xml_id!r}: priority={self.priority!r} invalid "
                f"(allowed: {sorted(VALID_TASK_PRIORITIES)}, see "
                f"addons/project/models/project_task.py)."
            )


@dataclass
class MaintenanceEquipmentCategory:
    """``maintenance.equipment.category`` (module ``maintenance``, Community).

    Verified against addons/maintenance/models/maintenance.py: only ``name`` is
    required; ``company_id`` defaults to ``env.company``. (verified-patterns 4.22)
    """

    xml_id: str
    name: str
    note: str | None = None


@dataclass
class MaintenanceEquipment:
    """``maintenance.equipment``.

    Verified: only ``name`` is required. ``effective_date`` (required in the
    mixin) has a default of ``context_today`` and is left to the ORM.
    ``serial_no`` is UNIQUE. ``category_id``/``partner_id`` are ``check_company``
    and must belong to the demo company. (verified-patterns 4.22)
    """

    xml_id: str
    name: str
    category_xmlid: str | None = None
    partner_xmlid: str | None = None
    serial_no: str | None = None
    model: str | None = None
    assign_date: str | None = None
    warranty_date: str | None = None
    cost: float | None = None
    note: str | None = None


@dataclass
class MaintenanceRequest:
    """``maintenance.request``.

    Verified: only ``name`` is required; ``company_id`` is required with default
    ``env.company`` and ``maintenance_team_id`` is required with a default that
    searches a team for the company (the engine creates a demo team explicitly).
    ``stage_id`` defaults to the first stage (``maintenance.stage_0`` "New
    Request"). ``create()`` clears ``close_date`` when the stage is not done and
    fills it when the stage is done. (verified-patterns 4.22)
    """

    xml_id: str
    name: str
    equipment_xmlid: str | None = None
    maintenance_type: str = "corrective"
    stage_xmlid: str = "maintenance.stage_0"
    priority: str | None = None
    description: str | None = None
    request_date: str | None = None
    schedule_date: str | None = None
    close_date: str | None = None

    def __post_init__(self) -> None:
        if self.maintenance_type not in VALID_MAINTENANCE_TYPES:
            raise SpecError(
                f"MaintenanceRequest {self.xml_id!r}: maintenance_type="
                f"{self.maintenance_type!r} invalid (allowed: "
                f"{sorted(VALID_MAINTENANCE_TYPES)}, see maintenance/models/maintenance.py)."
            )
        if self.priority is not None and self.priority not in VALID_TASK_PRIORITIES:
            raise SpecError(
                f"MaintenanceRequest {self.xml_id!r}: priority={self.priority!r} invalid "
                f"(allowed: {sorted(VALID_TASK_PRIORITIES)})."
            )


@dataclass
class QualityPoint:
    """``quality.point`` (Quality app ``quality_control``, Enterprise).

    Verified: ``name``, ``team_id``, ``picking_type_ids``, ``company_id`` and
    ``test_type_id`` are required; ``team_id``/``test_type_id`` have defaults.
    The engine sets the company's manufacturing operation type as
    ``picking_type_ids`` (so ``quality`` requires ``mrp``) and uses the shipped
    global team ``quality.quality_alert_team0``. ``test_type`` is the
    ``technical_name`` of ``quality.point.test_type`` (passfail/measure).
    ``measure_on='move_line'`` is forbidden with an mrp operation type.
    (verified-patterns 4.24)
    """

    xml_id: str
    name: str
    title: str | None = None
    product_xmlids: list[str] = field(default_factory=list)
    test_type: str = "passfail"
    measure_on: str = "product"
    note: str | None = None

    def __post_init__(self) -> None:
        if self.test_type not in VALID_QUALITY_TEST_TYPES:
            raise SpecError(
                f"QualityPoint {self.xml_id!r}: test_type={self.test_type!r} invalid "
                f"(allowed: {sorted(VALID_QUALITY_TEST_TYPES)})."
            )
        if self.measure_on not in VALID_QUALITY_MEASURE_ON:
            raise SpecError(
                f"QualityPoint {self.xml_id!r}: measure_on={self.measure_on!r} invalid "
                f"(allowed: {sorted(VALID_QUALITY_MEASURE_ON)}; 'move_line' is forbidden "
                f"with an mrp operation type)."
            )


@dataclass
class QualityCheck:
    """``quality.check``.

    Verified: ``team_id``/``company_id``/``test_type_id``/``measure_on`` are
    required but have defaults; setting ``point_id`` computes title/note/team/
    test_type/measure_on from the point. ``create()`` only fills ``name`` from a
    sequence (no business logic). A check's ``product_id`` must be one of the
    linked production order's finished products
    (``_check_allowed_product_ids_with_production``). (verified-patterns 4.24)
    """

    xml_id: str
    point_xmlid: str
    production_xmlid: str | None = None
    product_xmlid: str | None = None
    quality_state: str = "none"
    note: str | None = None

    def __post_init__(self) -> None:
        if self.quality_state not in VALID_QUALITY_STATES:
            raise SpecError(
                f"QualityCheck {self.xml_id!r}: quality_state={self.quality_state!r} "
                f"invalid (allowed: {sorted(VALID_QUALITY_STATES)})."
            )


@dataclass
class QualityAlert:
    """``quality.alert``.

    Verified: ``company_id`` and ``team_id`` are required with defaults;
    ``stage_id`` defaults to the first shipped stage
    (``quality.quality_alert_stage_0`` "New"). ``partner_id`` is ``check_company``.
    (verified-patterns 4.24)
    """

    xml_id: str
    name: str
    product_xmlid: str | None = None
    partner_xmlid: str | None = None
    production_xmlid: str | None = None
    stage_xmlid: str = "quality.quality_alert_stage_0"
    priority: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        if self.priority is not None and self.priority not in VALID_TASK_PRIORITIES:
            raise SpecError(
                f"QualityAlert {self.xml_id!r}: priority={self.priority!r} invalid "
                f"(allowed: {sorted(VALID_TASK_PRIORITIES)})."
            )


@dataclass
class SubscriptionLine:
    product_xmlid: str
    qty: float = 1.0
    description: str | None = None


@dataclass
class Subscription:
    """A recurring subscription (module ``sale_subscription``, Enterprise).

    In Odoo 19 there is NO ``sale.subscription`` model: a subscription is a
    ``sale.order`` with ``plan_id`` set (``is_subscription`` is computed from it).
    Verified: creating it in ``state='draft'`` is safe - no invoices/pickings are
    generated (invoices only come from the recurring cron/action), the Python
    constraint ``_constraint_subscription_plan`` exempts draft orders, and
    ``create()`` only defaults ``subscription_state`` to ``'1_draft'``. Lines of
    ``recurring_invoice`` products become recurring.
    (verified-patterns 4.25)
    """

    xml_id: str
    partner_xmlid: str
    plan: str = "month"
    state: str = "draft"
    start_date: str | None = None
    lines: list[SubscriptionLine] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.plan not in VALID_SUBSCRIPTION_PLANS:
            raise SpecError(
                f"Subscription {self.xml_id!r}: plan={self.plan!r} invalid "
                f"(allowed: {sorted(VALID_SUBSCRIPTION_PLANS)}; only these two plans "
                f"ship as data with sale_subscription)."
            )
        if self.state not in SAFE_SALE_ORDER_STATES:
            raise SpecError(
                f"Subscription {self.xml_id!r}: state={self.state!r} is not among the "
                f"verified safe values {sorted(SAFE_SALE_ORDER_STATES)} - a draft "
                f"subscription never triggers invoice generation (verified-patterns 4.25)."
            )


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
    quotation_templates: list[QuotationTemplate] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    project_task_stages: list[ProjectTaskStage] = field(default_factory=list)
    project_tasks: list[ProjectTask] = field(default_factory=list)
    # Maintenance (module `maintenance`, Community).
    maintenance_equipment_categories: list[MaintenanceEquipmentCategory] = field(default_factory=list)
    maintenance_equipment: list[MaintenanceEquipment] = field(default_factory=list)
    maintenance_requests: list[MaintenanceRequest] = field(default_factory=list)
    # Quality control (app `quality_control`, Enterprise; requires mrp).
    quality_points: list[QualityPoint] = field(default_factory=list)
    quality_checks: list[QualityCheck] = field(default_factory=list)
    quality_alerts: list[QualityAlert] = field(default_factory=list)
    # Subscriptions (app `sale_subscription`, Enterprise).
    subscriptions: list[Subscription] = field(default_factory=list)
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
        for template in self.quotation_templates:
            for line in template.lines:
                _require(
                    line.product_xmlid, product_ids,
                    f"QuotationTemplate {template.xml_id}: line product_xmlid",
                )
        project_ids = {p.xml_id for p in self.projects}
        task_stage_ids = {s.xml_id for s in self.project_task_stages}
        if self.project_task_stages and not self.projects:
            raise SpecError(
                "project_task_stages present but no projects: a task stage is only "
                "visible inside the projects it is linked to (project.task.type "
                "user_id/project_ids); without a project it becomes a personal stage. "
                "Add the project(s) or drop the stages."
            )
        for project in self.projects:
            if project.partner_xmlid:
                _require(project.partner_xmlid, partner_ids, f"Project {project.xml_id}: partner_xmlid")
        for task in self.project_tasks:
            _require(task.project_xmlid, project_ids, f"ProjectTask {task.xml_id}: project_xmlid")
            if task.stage_xmlid:
                _require(task.stage_xmlid, task_stage_ids, f"ProjectTask {task.xml_id}: stage_xmlid")
            if task.partner_xmlid:
                _require(task.partner_xmlid, partner_ids, f"ProjectTask {task.xml_id}: partner_xmlid")

        maintenance_category_ids = {c.xml_id for c in self.maintenance_equipment_categories}
        maintenance_equipment_ids = {e.xml_id for e in self.maintenance_equipment}
        for equipment in self.maintenance_equipment:
            if equipment.category_xmlid:
                _require(equipment.category_xmlid, maintenance_category_ids,
                         f"MaintenanceEquipment {equipment.xml_id}: category_xmlid")
            if equipment.partner_xmlid:
                _require(equipment.partner_xmlid, partner_ids,
                         f"MaintenanceEquipment {equipment.xml_id}: partner_xmlid")
        for request in self.maintenance_requests:
            if request.equipment_xmlid:
                _require(request.equipment_xmlid, maintenance_equipment_ids,
                         f"MaintenanceRequest {request.xml_id}: equipment_xmlid")

        # Quality points need the company warehouse's manufacturing operation
        # type as picking_type_ids, which only exists with mrp (the `quality`
        # bundle therefore requires `mrp`). (verified-patterns 4.24)
        if self.quality_points and not self.needs_mrp:
            raise SpecError(
                "quality_points present but no boms/manufacturing_orders: a quality "
                "point's picking_type_ids uses the warehouse manufacturing operation "
                "type (mrp), so the `quality` bundle requires `mrp`."
            )
        manufacturing_order_ids = {mo.xml_id for mo in self.manufacturing_orders}
        quality_point_ids = {p.xml_id for p in self.quality_points}
        for point in self.quality_points:
            for product_xmlid in point.product_xmlids:
                _require(product_xmlid, product_ids,
                         f"QualityPoint {point.xml_id}: product_xmlids")
        for check in self.quality_checks:
            _require(check.point_xmlid, quality_point_ids, f"QualityCheck {check.xml_id}: point_xmlid")
            if check.production_xmlid:
                _require(check.production_xmlid, manufacturing_order_ids,
                         f"QualityCheck {check.xml_id}: production_xmlid")
            if check.product_xmlid:
                _require(check.product_xmlid, product_ids, f"QualityCheck {check.xml_id}: product_xmlid")
        for alert in self.quality_alerts:
            if alert.product_xmlid:
                _require(alert.product_xmlid, product_ids, f"QualityAlert {alert.xml_id}: product_xmlid")
            if alert.partner_xmlid:
                _require(alert.partner_xmlid, partner_ids, f"QualityAlert {alert.xml_id}: partner_xmlid")
            if alert.production_xmlid:
                _require(alert.production_xmlid, manufacturing_order_ids,
                         f"QualityAlert {alert.xml_id}: production_xmlid")
        for subscription in self.subscriptions:
            _require(subscription.partner_xmlid, partner_ids,
                     f"Subscription {subscription.xml_id}: partner_xmlid")
            for line in subscription.lines:
                _require(line.product_xmlid, product_ids,
                         f"Subscription {subscription.xml_id}: line product_xmlid")

        # sale_subscription._constraint_subscription_plan raises on a non-draft
        # sale.order that has a recurring product line but no plan_id
        # (sale_subscription/models/sale_order.py _check_recurring_plan_mismatch).
        # Draft orders are exempt; subscriptions carry a plan. (verified-patterns 4.25)
        recurring_product_ids = {p.xml_id for p in self.products if p.recurring_invoice}
        for order in ([self.quotation] if self.quotation else []) + self.example_orders:
            if order.state != "draft":
                for line in order.lines:
                    if line.product_xmlid in recurring_product_ids:
                        raise SpecError(
                            f"SaleOrder {order.xml_id}: recurring product "
                            f"{line.product_xmlid!r} on a non-draft order (state="
                            f"{order.state!r}) needs a subscription plan - "
                            f"sale_subscription raises 'Please add a recurring plan on the "
                            f"subscription or remove the recurring product'. Use "
                            f"state='draft' or the subscriptions section "
                            f"(verified-patterns 4.25)."
                        )

    @property
    def needs_project(self) -> bool:
        return bool(self.projects) or bool(self.project_task_stages) or bool(self.project_tasks)

    @property
    def needs_maintenance(self) -> bool:
        return bool(self.maintenance_equipment_categories) or bool(self.maintenance_equipment) \
            or bool(self.maintenance_requests)

    @property
    def needs_quality(self) -> bool:
        return bool(self.quality_points) or bool(self.quality_checks) or bool(self.quality_alerts)

    @property
    def needs_subscriptions(self) -> bool:
        return bool(self.subscriptions)

    @property
    def needs_field_service(self) -> bool:
        return any(project.is_fsm for project in self.projects)

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
        # Quality points use the warehouse manufacturing operation type as
        # picking_type_ids (verified-patterns.md 4.24).
        return self.needs_purchase or self.needs_stock or self.needs_mrp or bool(self.quality_points)

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

    @property
    def resolved_maintenance_team_name(self) -> str:
        return default_team_names(self.resolved_language)[2]


def _require(xmlid: str, known: set[str], where: str) -> None:
    if xmlid not in known:
        raise SpecError(
            f"{where} references {xmlid!r}, which is not an xml_id defined in this "
            f"specification. Typo or missing record?"
        )

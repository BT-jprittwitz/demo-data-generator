"""Capability bundles: the selection vocabulary of the generator.

A **bundle** groups the building blocks (spec sections, named after the Odoo
models they write) of one process/app and declares

- the Odoo ``apps`` (modules) it needs,
- the other bundles it ``requires`` (process dependencies).

Choosing a bundle closes its requirements automatically (e.g. ``mrp`` pulls
``stock`` = the demo warehouse and ``products`` = the catalog), so a demo is
never installed half-configured ("producing without a warehouse does not work").

Bundles are generic capabilities, **not** industry profiles: there is no catalog
of canned verticals (see ``ROADMAP.md``, principle "No fixed industry verticals").
The LLM decides which bundles fit a customer by reasoning about the company
(e.g. medical devices -> quality control). If the reasoning needs an app without
a bundle, that is a demand signal (verify + build the bundle), not something to
fake.

The spec sections stay the data payload (single source of truth:
``engine/model.py``); bundles only select them.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Iterable

from .model import CustomerSpec

# Canonical order of the spec sections (kept in sync with the data-file order in
# engine/manifest.py). Used to render resolved bundles deterministically.
SECTION_ORDER: tuple[str, ...] = (
    "company",
    "partners",
    "products",
    "boms",
    "manufacturing_orders",
    "quotation",
    "quotation_templates",
    "example_orders",
    "crm_leads",
    "purchase_orders",
    "stock_quants",
    "invoices",
    "helpdesk_tickets",
    "projects",
    "project_task_stages",
    "project_tasks",
)


@dataclass(frozen=True)
class Bundle:
    id: str
    label: str
    sections: tuple[str, ...] = ()
    apps: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    relevant_when: str = ""


BUNDLES: dict[str, Bundle] = {
    "company": Bundle(
        id="company",
        label="Company",
        sections=("company",),
        relevant_when="always - every module creates its own res.company.",
    ),
    "contacts": Bundle(
        id="contacts",
        label="Contacts / partners",
        sections=("partners",),
        relevant_when=(
            "named customers, suppliers or people appear anywhere "
            "(sales, purchasing, CRM, support)."
        ),
    ),
    "products": Bundle(
        id="products",
        label="Product catalog",
        sections=("products",),
        relevant_when="the company sells or buys goods or services.",
    ),
    "sales": Bundle(
        id="sales",
        label="Sales / quotations",
        sections=("quotation", "quotation_templates", "example_orders"),
        apps=("sale_management",),
        requires=("products", "contacts"),
        relevant_when=(
            "quotes, sales orders and reusable quotation templates to customers."
        ),
    ),
    "crm": Bundle(
        id="crm",
        label="CRM pipeline",
        sections=("crm_leads",),
        apps=("crm",),
        requires=("contacts",),
        relevant_when="a lead/opportunity pipeline before or alongside quoting.",
    ),
    "project": Bundle(
        id="project",
        label="Projects",
        sections=("projects", "project_task_stages", "project_tasks"),
        apps=("project",),
        requires=("contacts",),
        relevant_when=(
            "delivery/implementation work is tracked as projects with tasks and "
            "stages (services, construction, IT rollout, ...)."
        ),
    ),
    "purchase": Bundle(
        id="purchase",
        label="Purchasing",
        sections=("purchase_orders",),
        apps=("purchase",),
        requires=("products", "contacts", "stock"),
        relevant_when="procurement of goods/services from suppliers.",
    ),
    "stock": Bundle(
        id="stock",
        label="Inventory / warehouse",
        sections=("stock_quants",),
        apps=("stock",),
        requires=("products",),
        relevant_when="the company holds, stores or ships inventory.",
    ),
    "mrp": Bundle(
        id="mrp",
        label="Manufacturing",
        sections=("boms", "manufacturing_orders"),
        apps=("mrp",),
        requires=("stock", "products"),
        relevant_when=(
            "the company manufactures goods from components (bills of materials); "
            "implies a warehouse."
        ),
    ),
    "accounting": Bundle(
        id="accounting",
        label="Accounting / invoices",
        sections=("invoices",),
        apps=("account",),
        requires=("products", "contacts"),
        relevant_when=(
            "posted customer/vendor invoices; needs a chart of accounts "
            "(company.chart_template)."
        ),
    ),
    "helpdesk": Bundle(
        id="helpdesk",
        label="Helpdesk / service tickets",
        sections=("helpdesk_tickets",),
        apps=("helpdesk",),
        requires=("contacts",),
        relevant_when="after-sales support / service tickets (Enterprise).",
    ),
}


class BundleError(ValueError):
    """Unknown bundle, cyclic requirement or an invalid bundle definition."""


@dataclass(frozen=True)
class Resolved:
    bundle_ids: tuple[str, ...]
    sections: tuple[str, ...]
    apps: tuple[str, ...]


def resolve(selected: Iterable[str], bundles: dict[str, Bundle] = BUNDLES) -> Resolved:
    """Transitive closure of the selected bundles.

    Returns the bundles in dependency order, the union of their spec sections
    (canonically ordered) and the union of their apps. Raises ``BundleError`` for
    unknown bundles or cyclic requirements.
    """
    ordered: list[str] = []
    done: set[str] = set()
    visiting: set[str] = set()

    def visit(bundle_id: str, chain: list[str]) -> None:
        if bundle_id in done:
            return
        if bundle_id in visiting:
            raise BundleError(
                f"cyclic bundle requirement: {' -> '.join(chain + [bundle_id])}"
            )
        if bundle_id not in bundles:
            raise BundleError(
                f"unknown bundle {bundle_id!r}. Known: {sorted(bundles)}."
            )
        visiting.add(bundle_id)
        for requirement in bundles[bundle_id].requires:
            visit(requirement, chain + [bundle_id])
        visiting.discard(bundle_id)
        done.add(bundle_id)
        ordered.append(bundle_id)

    for bundle_id in dict.fromkeys(selected):  # dedupe, keep order
        visit(bundle_id, [])

    sections: set[str] = set()
    apps: list[str] = []
    for bundle_id in ordered:
        bundle = bundles[bundle_id]
        sections.update(bundle.sections)
        for app in bundle.apps:
            if app not in apps:
                apps.append(app)

    return Resolved(
        bundle_ids=tuple(ordered),
        sections=tuple(s for s in SECTION_ORDER if s in sections),
        apps=tuple(apps),
    )


def validate_bundles(bundles: dict[str, Bundle] = BUNDLES) -> list[str]:
    """Structural checks; returns a list of problems ([] = ok)."""
    problems: list[str] = []
    spec_fields = {f.name for f in dataclasses.fields(CustomerSpec)}

    for bundle_id, bundle in bundles.items():
        if bundle_id != bundle.id:
            problems.append(f"bundle key {bundle_id!r} != id {bundle.id!r}")
        for section in bundle.sections:
            if section not in SECTION_ORDER:
                problems.append(f"{bundle_id}: section {section!r} is not a known spec section")
            elif section not in spec_fields:
                problems.append(f"{bundle_id}: section {section!r} is not a CustomerSpec field")
        for requirement in bundle.requires:
            if requirement not in bundles:
                problems.append(f"{bundle_id}: requires unknown bundle {requirement!r}")

    for bundle_id in bundles:
        try:
            resolve([bundle_id], bundles)
        except BundleError as exc:
            problems.append(str(exc))

    return problems


def render_capabilities_markdown(bundles: dict[str, Bundle] = BUNDLES) -> str:
    """Markdown catalog for the skill reference (generated, not hand-edited)."""
    lines = [
        "# Capability bundles (selection menu)",
        "",
        "The engine composes each customer module from verified **building blocks**",
        "(spec sections, named after the Odoo models they write). There is no fixed",
        "industry profile - see `ROADMAP.md`, principle *\"No fixed industry verticals\"*.",
        "",
        "A **bundle** groups the blocks of one process/app, lists the Odoo `apps` it",
        "needs and the other bundles it `requires`. Selecting a bundle closes its",
        "requirements automatically: choosing `mrp` also pulls `stock` (the demo",
        "warehouse) and `products` (the catalog) - producing without a warehouse does",
        "not work. A selected app is never installed empty: its bundle brings the demo",
        "data for its sub-models.",
        "",
        "Scaffold a spec skeleton for the chosen bundles:",
        "`python3 -m engine.cli new --with <bundle,...> --name ... --country ...`.",
        "",
        "> Generated by `python3 -m engine.cli capabilities`; do not edit by hand.",
        "> Source of truth: `engine/bundles.py`.",
        "",
        "## Reason about adjacent processes",
        "",
        "Do not just map the obvious process - use what you know about the company to",
        "ask what *else* matters. Examples:",
        "",
        "- Medical devices / pharma / food / aerospace -> quality control, batch/lot",
        "  traceability.",
        "- Regulated or approval-heavy processes -> approvals.",
        "- Maintenance-intensive assets -> maintenance.",
        "- Recurring revenue -> subscriptions.",
        "",
        "If the reasoning needs an app we have **no bundle** for, say so explicitly and",
        "treat it as a demand signal (verify against the Odoo 19.0 source, then build",
        "the bundle) - do not fake data for it.",
        "",
        "## Catalog",
        "",
        "| Bundle | Sections | Apps | Requires | Relevant when |",
        "|---|---|---|---|---|",
    ]
    for bundle in bundles.values():
        lines.append(
            "| `{id}` | {sections} | {apps} | {requires} | {when} |".format(
                id=bundle.id,
                sections=", ".join(f"`{s}`" for s in bundle.sections) or "-",
                apps=", ".join(f"`{a}`" for a in bundle.apps) or "-",
                requires=", ".join(f"`{r}`" for r in bundle.requires) or "-",
                when=bundle.relevant_when,
            )
        )
    lines.append("")
    return "\n".join(lines)

"""Recommended minimum demo-data volume ("rich demo" tier).

The generator emits exactly the records present in the spec - there is no
built-in data volume. To keep delivered packages convincing, ``engine.cli
generate`` warns when a *used* section stays below the recommended minimum.

These are warnings, never errors: a focused package may deliberately stay
smaller, and the ZIP is still built. Only sections that are already used
(count > 0) are checked, so a deliberately omitted section never warns.
Source of truth for the numbers; the table in ``reference/spec-format.md``
mirrors them.
"""
from __future__ import annotations

from .model import CustomerSpec
from .validate import Finding

# Recommended minimum record count per object type ("rich demo" tier: roughly
# 3-4x the original example packages).
RECOMMENDED_VOLUME: dict[str, int] = {
    "partners": 30,
    "products": 25,
    "invoices": 10,
    "crm_leads": 15,
    "purchase_orders": 10,
    "example_orders": 12,
    "helpdesk_tickets": 12,
    "quotation_templates": 4,
    "projects": 3,
    "project_tasks": 12,
    "manufacturing_orders": 8,
    "stock_quants": 10,
    "subscriptions": 6,
    "maintenance_equipment": 6,
    "maintenance_requests": 8,
    "quality_points": 4,
    "quality_checks": 6,
    "quality_alerts": 4,
}


def _section_counts(spec: CustomerSpec) -> dict[str, int]:
    return {
        "partners": len(spec.partners),
        "products": len(spec.products),
        "invoices": len(spec.invoices),
        "crm_leads": len(spec.crm_leads),
        "purchase_orders": len(spec.purchase_orders),
        # A single draft quotation counts towards the example orders.
        "example_orders": len(spec.example_orders) + (1 if spec.quotation else 0),
        "helpdesk_tickets": len(spec.helpdesk_tickets),
        "quotation_templates": len(spec.quotation_templates),
        "projects": len(spec.projects),
        "project_tasks": len(spec.project_tasks),
        "manufacturing_orders": len(spec.manufacturing_orders),
        "stock_quants": len(spec.stock_quants),
        "subscriptions": len(spec.subscriptions),
        "maintenance_equipment": len(spec.maintenance_equipment),
        "maintenance_requests": len(spec.maintenance_requests),
        "quality_points": len(spec.quality_points),
        "quality_checks": len(spec.quality_checks),
        "quality_alerts": len(spec.quality_alerts),
    }


def check_data_volume(spec: CustomerSpec) -> list[Finding]:
    """Warn when a used section is below the recommended demo volume."""
    findings: list[Finding] = []
    for section, count in _section_counts(spec).items():
        minimum = RECOMMENDED_VOLUME[section]
        if 0 < count < minimum:
            findings.append(Finding(
                "warning",
                f"{section}: {count} record(s) - recommended for a convincing demo: "
                f"at least {minimum} (reference/spec-format.md, 'Recommended data volume').",
            ))
    return findings

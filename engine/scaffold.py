"""Scaffold a customer specification (JSON) from capability bundles.

``engine.cli new --with <bundles>`` calls this: it resolves the bundle
dependencies (``engine.bundles.resolve``) and writes a starter spec that contains
exactly the required sections, so nothing (e.g. the warehouse pulled in by mrp)
can be forgotten. It only creates the *structure* + the company block; the
content is filled in afterwards.

No fixed industry profiles: the bundles are chosen per customer (see
ROADMAP.md, principle "No fixed industry verticals").
"""
from __future__ import annotations

import json
import unicodedata
from typing import Iterable

from .bundles import resolve

# Section -> placeholder value. "quotation" is a single object (else None); all
# other sections are lists.
SINGLE_SECTIONS = {"quotation"}


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(c if c.isalnum() else "_" for c in ascii_name.lower())
    return "_".join(part for part in cleaned.split("_") if part)


def default_technical_name(name: str) -> str:
    return f"bt_demo_{slugify(name)}"


def normalize_country(country: str) -> str:
    country = country.strip()
    return country if "." in country else f"base.{country.lower()}"


def build_skeleton(
    selected_bundles: Iterable[str],
    *,
    name: str,
    country: str,
    street: str | None = None,
    city: str | None = None,
    zip_code: str | None = None,
    vat: str | None = None,
    currency_xmlid: str | None = None,
    chart_template: str | None = None,
    language: str | None = None,
    technical_name: str | None = None,
    title: str | None = None,
    summary: str | None = None,
    description: str | None = None,
) -> dict:
    """Build the spec skeleton. Raises ``BundleError`` for an unknown bundle."""
    resolved = resolve(selected_bundles)
    technical = technical_name or default_technical_name(name)

    skeleton: dict = {
        "module": {
            "technical_name": technical,
            "title": title or f"Demo Data - {name}",
            "summary": summary or "TODO: one sentence.",
            "description": description or "TODO: longer description of the demo data.",
        },
        "company": {
            "name": name,
            "street": street or "TODO",
            "city": city or "TODO",
            "zip": zip_code or "TODO",
            "country_xmlid": normalize_country(country),
        },
    }
    if vat:
        skeleton["company"]["vat"] = vat
    if currency_xmlid:
        skeleton["company"]["currency_xmlid"] = currency_xmlid
    if chart_template:
        skeleton["company"]["chart_template"] = chart_template
    if language:
        skeleton["language"] = language

    for section in resolved.sections:
        if section == "company":
            continue
        skeleton[section] = None if section in SINGLE_SECTIONS else []

    return skeleton


def to_json(skeleton: dict) -> str:
    return json.dumps(skeleton, indent=2, ensure_ascii=False) + "\n"

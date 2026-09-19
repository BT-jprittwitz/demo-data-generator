"""Generates a JSON schema from the spec dataclasses in model.py.

The dataclasses remain the single source of truth. This module derives a
machine-readable schema for editors/LLMs from them (autocompletion,
type checking). A test (`engine/tests/test_engine.py`) ensures that
`engine/spec/spec.schema.json` matches the generated state exactly - no drift.

Regenerate:
    python3 -m engine.cli spec-schema --out engine/spec/spec.schema.json
"""
from __future__ import annotations

import dataclasses
import json
import types
import typing
from pathlib import Path

from . import model

SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"

# Fields with restricted values. The values come directly from the constants in
# model.py, so that schema and validation do not drift apart.
_ENUMS: dict[tuple[str, str], set[str]] = {
    ("Product", "type"): model.VALID_PRODUCT_TYPES,
    ("CrmLead", "type"): model.VALID_CRM_LEAD_TYPES,
    ("SaleOrder", "state"): model.SAFE_SALE_ORDER_STATES,
    ("PurchaseOrder", "state"): model.SAFE_PURCHASE_ORDER_STATES,
    ("Invoice", "move_type"): model.VALID_INVOICE_MOVE_TYPES,
    ("CustomerSpec", "accounting_app"): {"full", "invoicing"},
}


def _schema_for_type(tp: typing.Any) -> dict:
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if origin is types.UnionType or origin is typing.Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _schema_for_type(non_none[0])
        return {"anyOf": [_schema_for_type(a) for a in non_none]}
    if origin in (list, typing.List):
        return {"type": "array", "items": _schema_for_type(args[0])}
    if dataclasses.is_dataclass(tp):
        return {"$ref": f"#/$defs/{tp.__name__}"}
    if tp is str:
        return {"type": "string"}
    if tp is bool:
        return {"type": "boolean"}
    if tp is int:
        return {"type": "integer"}
    if tp is float:
        return {"type": "number"}
    return {}


def _iter_dataclasses(tp: typing.Any):
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if origin is types.UnionType or origin is typing.Union:
        for arg in args:
            yield from _iter_dataclasses(arg)
    elif origin in (list, typing.List):
        yield from _iter_dataclasses(args[0])
    elif dataclasses.is_dataclass(tp):
        yield tp


def build_schema() -> dict:
    defs: dict[str, dict] = {}
    seen: set[str] = set()

    def add(cls: type) -> None:
        if cls.__name__ in seen:
            return
        seen.add(cls.__name__)
        hints = typing.get_type_hints(cls)
        properties: dict[str, dict] = {}
        required: list[str] = []
        for f in dataclasses.fields(cls):
            tp = hints[f.name]
            fragment = _schema_for_type(tp)
            enum = _ENUMS.get((cls.__name__, f.name))
            if enum:
                fragment = {**fragment, "enum": sorted(enum)}
            properties[f.name] = fragment
            if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
                required.append(f.name)
            for sub in _iter_dataclasses(tp):
                add(sub)
        entry: dict = {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        }
        if required:
            entry["required"] = required
        defs[cls.__name__] = entry

    add(model.CustomerSpec)
    return {
        "$schema": SCHEMA_DRAFT,
        "title": "Odoo Demo Data Customer Specification",
        "type": "object",
        "$ref": "#/$defs/CustomerSpec",
        "$defs": defs,
    }


def write_schema(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_schema(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path

"""Low-level helpers to assemble well-formed Odoo demo data XML.

Uses xml.etree.ElementTree instead of string concatenation so that well-formedness
and correct escaping (quotes/special characters in customer data such as
company names) are guaranteed by the stdlib, not by manual f-string
assembly.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET


def field_el(name: str, *, text=None, ref: str | None = None, eval_: str | None = None, model: str | None = None) -> ET.Element:
    attrs = {"name": name}
    if model is not None:
        attrs["model"] = model
    if ref is not None:
        attrs["ref"] = ref
    if eval_ is not None:
        attrs["eval"] = eval_
    el = ET.Element("field", attrs)
    if text is not None:
        el.text = _fmt(text)
    return el


def _fmt(value) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def record_el(model: str, xml_id: str, fields: list[ET.Element], context: str | None = None) -> ET.Element:
    attrs = {"id": xml_id, "model": model}
    if context is not None:
        attrs["context"] = context
    el = ET.Element("record", attrs)
    for f in fields:
        el.append(f)
    return el


def render_odoo_file(records: list[ET.Element], noupdate: bool = False) -> str:
    root = ET.Element("odoo")
    container = root
    if noupdate:
        container = ET.SubElement(root, "data", {"noupdate": "1"})
    for r in records:
        container.append(r)
    ET.indent(root, space="    ")
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + body + "\n"

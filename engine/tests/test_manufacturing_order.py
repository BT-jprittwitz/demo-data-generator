"""Tests for the mrp.production building block (verified against odoo/odoo@19.0)."""
from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from engine.manifest import depends
from engine.model import ManufacturingOrder, SpecError
from engine.records import mrp_production_record
from engine.spec_loader import load_spec


def _spec(**overrides: object):
    base: dict = {
        "module": {"technical_name": "bt_demo_t", "title": "T", "summary": "s"},
        "company": {
            "name": "C",
            "street": "S",
            "city": "Ci",
            "zip": "1",
            "country_xmlid": "base.ch",
        },
        "products": [
            {"xml_id": "p_fin", "name": "Fin", "type": "consu", "sale_ok": True, "purchase_ok": False},
            {"xml_id": "p_comp", "name": "Comp", "type": "consu", "sale_ok": False, "purchase_ok": True},
        ],
        "boms": [
            {"xml_id": "b1", "product_xmlid": "p_fin", "lines": [{"product_xmlid": "p_comp", "qty": 2.0}]}
        ],
    }
    base.update(overrides)
    return load_spec(base)


class ManufacturingOrderTests(unittest.TestCase):
    def test_qty_must_be_positive(self) -> None:
        with self.assertRaises(SpecError):
            ManufacturingOrder(xml_id="mo", product_xmlid="p_fin", qty=0.0)

    def test_mo_requires_existing_product(self) -> None:
        with self.assertRaises(SpecError):
            _spec(manufacturing_orders=[{"xml_id": "mo", "product_xmlid": "missing", "qty": 1.0}])

    def test_mo_requires_boms(self) -> None:
        with self.assertRaises(SpecError):
            _spec(boms=[], manufacturing_orders=[{"xml_id": "mo", "product_xmlid": "p_fin", "qty": 1.0}])

    def test_mo_bom_reference_must_exist(self) -> None:
        with self.assertRaises(SpecError):
            _spec(manufacturing_orders=[{"xml_id": "mo", "product_xmlid": "p_fin", "bom_xmlid": "nope", "qty": 1.0}])

    def test_manufacturing_implies_warehouse_but_not_vice_versa(self) -> None:
        spec = _spec(manufacturing_orders=[{"xml_id": "mo", "product_xmlid": "p_fin", "bom_xmlid": "b1", "qty": 1.0}])
        self.assertTrue(spec.needs_mrp)
        self.assertTrue(spec.needs_warehouse)
        deps = depends(spec)
        self.assertIn("mrp", deps)
        self.assertIn("stock", deps)
        # A warehouse-only spec must NOT pull manufacturing.
        warehouse_only = _spec(boms=[], stock_quants=[{"product_xmlid": "p_fin", "qty": 5.0}])
        self.assertTrue(warehouse_only.needs_warehouse)
        self.assertFalse(warehouse_only.needs_mrp)
        self.assertNotIn("mrp", depends(warehouse_only))

    def test_record_sets_picking_type_and_never_state(self) -> None:
        spec = _spec(manufacturing_orders=[{"xml_id": "mo", "product_xmlid": "p_fin", "bom_xmlid": "b1", "qty": 3.0}])
        element = mrp_production_record(spec.manufacturing_orders[0], "demo_company", "warehouse_demo", "de_CH")
        xml = ET.tostring(element, encoding="unicode")
        self.assertIn("manu_type_id", xml)
        self.assertIn("bom_id", xml)
        self.assertIn("product_qty", xml)
        self.assertNotIn('name="state"', xml)


if __name__ == "__main__":
    unittest.main()

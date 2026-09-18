"""Tests fuer die Generator-Engine. Reine Struktur-/Logiktests (kein Odoo-Kernel
noetig) - siehe generator/validate.py fuer die Grenzen der statischen Pruefung."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from generator.builder import write_module_dir
from generator.model import (
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
from generator.spec_loader import load_spec
from generator.validate import validate_module

EXAMPLE_SPEC_PATH = Path(__file__).resolve().parent.parent / "examples" / "muster_foerdertechnik.json"


def _minimal_spec(**overrides) -> CustomerSpec:
    defaults = dict(
        module=Module(technical_name="bt_demo_test", title="Test", summary="Test", description="Test"),
        company=Company(name="Test AG", street="Teststrasse 1", city="Teststadt", zip="1234", country_xmlid="base.ch"),
        products=[
            Product(xml_id="prod_a", name="Produkt A", type="consu", sale_ok=True, purchase_ok=False, standard_price=10.0),
        ],
    )
    defaults.update(overrides)
    return CustomerSpec(**defaults)


class ModelValidationTests(unittest.TestCase):
    def test_rejects_unsafe_sale_order_state(self):
        with self.assertRaises(SpecError):
            SaleOrder(xml_id="so1", partner_xmlid="p1", lines=[], state="sale")

    def test_accepts_safe_sale_order_states(self):
        SaleOrder(xml_id="so1", partner_xmlid="p1", lines=[], state="draft")
        SaleOrder(xml_id="so2", partner_xmlid="p1", lines=[], state="sent")

    def test_rejects_unknown_product_type(self):
        with self.assertRaises(SpecError):
            Product(xml_id="p1", name="X", type="storable", sale_ok=True, purchase_ok=False)

    def test_service_defaults_to_not_storable(self):
        p = Product(xml_id="svc", name="Service", type="service", sale_ok=True, purchase_ok=False)
        self.assertFalse(p.is_storable)

    def test_consu_defaults_to_storable(self):
        p = Product(xml_id="c1", name="Ware", type="consu", sale_ok=True, purchase_ok=False)
        self.assertTrue(p.is_storable)

    def test_rejects_duplicate_barcodes(self):
        with self.assertRaises(SpecError):
            _minimal_spec(products=[
                Product(xml_id="a", name="A", type="consu", sale_ok=True, purchase_ok=False, barcode="123"),
                Product(xml_id="b", name="B", type="consu", sale_ok=True, purchase_ok=False, barcode="123"),
            ])

    def test_rejects_dangling_bom_reference(self):
        with self.assertRaises(SpecError):
            _minimal_spec(boms=[Bom(xml_id="bom1", product_xmlid="does_not_exist", lines=[])])

    def test_rejects_dangling_sale_order_partner(self):
        with self.assertRaises(SpecError):
            _minimal_spec(
                example_orders=[
                    SaleOrder(xml_id="so1", partner_xmlid="missing_partner", lines=[
                        SaleOrderLine(product_xmlid="prod_a", qty=1.0, description="x"),
                    ])
                ]
            )


class BuilderAndValidateTests(unittest.TestCase):
    def test_example_spec_builds_and_validates_clean(self):
        data = json.loads(EXAMPLE_SPEC_PATH.read_text(encoding="utf-8"))
        spec = load_spec(data)
        with TemporaryDirectory() as tmp:
            module_dir = write_module_dir(spec, Path(tmp))
            findings = validate_module(module_dir)
            errors = [f for f in findings if f.level == "error"]
            self.assertEqual(errors, [], f"Unerwartete Validierungsfehler: {errors}")

    def test_standard_price_gets_company_context(self):
        spec = _minimal_spec()
        with TemporaryDirectory() as tmp:
            module_dir = write_module_dir(spec, Path(tmp))
            xml = (module_dir / "data" / "product_data.xml").read_text(encoding="utf-8")
            self.assertIn("allowed_company_ids", xml)

    def test_validate_flags_standard_price_without_context(self):
        # Simuliert den in HANDOVER.md 4.7 dokumentierten, im alten bt_demo_mfg.zip
        # tatsaechlich vorhandenen Bug: standard_price gesetzt, aber ohne context.
        with TemporaryDirectory() as tmp:
            module_dir = Path(tmp) / "bt_demo_broken"
            data_dir = module_dir / "data"
            data_dir.mkdir(parents=True)
            (module_dir / "__manifest__.py").write_text(
                '{"data": ["data/product_data.xml"]}', encoding="utf-8"
            )
            (data_dir / "product_data.xml").write_text(
                '<?xml version="1.0"?><odoo>'
                '<record id="p1" model="product.product">'
                '<field name="standard_price">10.0</field>'
                "</record></odoo>",
                encoding="utf-8",
            )
            findings = validate_module(module_dir)
            self.assertTrue(any("allowed_company_ids" in f.message for f in findings))

    def test_validate_flags_unsafe_sale_order_state_written_directly(self):
        with TemporaryDirectory() as tmp:
            module_dir = Path(tmp) / "bt_demo_broken2"
            data_dir = module_dir / "data"
            data_dir.mkdir(parents=True)
            (module_dir / "__manifest__.py").write_text(
                '{"data": ["data/so.xml"]}', encoding="utf-8"
            )
            (data_dir / "so.xml").write_text(
                '<?xml version="1.0"?><odoo>'
                '<record id="so1" model="sale.order">'
                '<field name="state">sale</field>'
                "</record></odoo>",
                encoding="utf-8",
            )
            findings = validate_module(module_dir)
            self.assertTrue(any("HANDOVER.md 4.3" in f.message for f in findings))


if __name__ == "__main__":
    unittest.main()

"""Tests for the generator engine. Pure structure/logic tests (no Odoo kernel
required) - see engine/validate.py for the limits of static validation."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from engine.builder import write_module_dir
from engine.model import (
    Bom,
    BomLine,
    Company,
    CustomerSpec,
    Invoice,
    InvoiceLine,
    Module,
    Partner,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    SaleOrder,
    SaleOrderLine,
    SpecError,
    StockQuant,
)
from engine.manifest import depends
from engine.schema import build_schema
from engine.spec_loader import load_spec
from engine.validate import validate_module

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_SPEC_PATH = REPO_ROOT / "examples" / "muster_foerdertechnik.json"
SCHEMA_PATH = REPO_ROOT / "engine" / "spec" / "spec.schema.json"


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


class SpecLoaderTests(unittest.TestCase):
    def _minimal(self, **overrides) -> dict:
        spec = {
            "module": {"technical_name": "bt_x", "title": "T", "summary": "S"},
            "company": {"name": "N", "street": "Weg 1", "city": "Stadt", "zip": "1",
                        "country_xmlid": "base.ch"},
        }
        spec.update(overrides)
        return spec

    def test_rejects_unknown_top_level_field(self):
        with self.assertRaises(SpecError):
            load_spec(self._minimal(produkts=[]))

    def test_rejects_unknown_nested_field(self):
        with self.assertRaises(SpecError):
            load_spec(self._minimal(products=[
                {"xml_id": "p", "name": "P", "type": "consu", "sale_ok": True,
                 "purchase_ok": False, "price": 1.0},
            ]))

    def test_accepts_minimal_spec(self):
        spec = load_spec(self._minimal())
        self.assertEqual(spec.module.technical_name, "bt_x")

    def test_spec_schema_is_up_to_date(self):
        self.assertTrue(SCHEMA_PATH.exists(), "engine/spec/spec.schema.json is missing")
        self.assertEqual(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")), build_schema())


class BuilderAndValidateTests(unittest.TestCase):
    def test_example_spec_builds_and_validates_clean(self):
        data = json.loads(EXAMPLE_SPEC_PATH.read_text(encoding="utf-8"))
        spec = load_spec(data)
        with TemporaryDirectory() as tmp:
            module_dir = write_module_dir(spec, Path(tmp))
            findings = validate_module(module_dir)
            errors = [f for f in findings if f.level == "error"]
            self.assertEqual(errors, [], f"Unexpected validation errors: {errors}")

    def test_standard_price_gets_company_context(self):
        spec = _minimal_spec()
        with TemporaryDirectory() as tmp:
            module_dir = write_module_dir(spec, Path(tmp))
            xml = (module_dir / "data" / "product_data.xml").read_text(encoding="utf-8")
            self.assertIn("allowed_company_ids", xml)

    def test_validate_flags_standard_price_without_context(self):
        # Simulates the bug documented in verified-patterns.md 4.7 and actually
        # present in the old bt_demo_mfg.zip: standard_price set, but without context.
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
            self.assertTrue(any("4.3" in f.message for f in findings))


class ErpBlockTests(unittest.TestCase):
    """New ERP building blocks (CRM, purchasing, stock, accounting, customer service)."""

    def _erp_spec(self, **overrides) -> CustomerSpec:
        base = dict(
            module=Module(technical_name="bt_demo_erp", title="ERP", summary="ERP", description="ERP"),
            company=Company(
                name="Test AG", street="Teststrasse 1", city="Teststadt", zip="1234",
                country_xmlid="base.ch", chart_template="ch",
            ),
            partners=[
                Partner(xml_id="p1", name="Kunde AG", country_xmlid="base.ch",
                        street="Weg 1", city="Stadt", zip="1111", customer_rank=1),
                Partner(xml_id="p2", name="Lieferant AG", country_xmlid="base.de",
                        street="Weg 2", city="Ort", zip="2222", supplier_rank=1, customer_rank=0),
            ],
            products=[
                Product(xml_id="prod_a", name="Ware A", type="consu", sale_ok=True,
                        purchase_ok=True, list_price=100.0, standard_price=40.0),
            ],
        )
        base.update(overrides)
        return CustomerSpec(**base)

    def test_purchase_order_state_is_restricted(self):
        with self.assertRaises(SpecError):
            PurchaseOrder(xml_id="po1", partner_xmlid="p2", state="purchase", lines=[
                PurchaseOrderLine(product_xmlid="prod_a", qty=1.0, price_unit=40.0, description="x"),
            ])

    def test_invoice_move_type_is_restricted(self):
        with self.assertRaises(SpecError):
            Invoice(xml_id="inv1", move_type="entry", partner_xmlid="p1",
                    invoice_date="2025-01-01", lines=[])

    def test_rejects_dangling_stock_quant_product(self):
        with self.assertRaises(SpecError):
            self._erp_spec(stock_quants=[StockQuant(product_xmlid="missing", qty=5.0)])

    def test_erp_spec_builds_and_validates_clean(self):
        spec = self._erp_spec(
            crm_leads=[],
            purchase_orders=[
                PurchaseOrder(xml_id="po1", partner_xmlid="p2", state="draft", lines=[
                    PurchaseOrderLine(product_xmlid="prod_a", qty=10.0, price_unit=40.0, description="Ware A"),
                ]),
            ],
            stock_quants=[StockQuant(product_xmlid="prod_a", qty=25.0)],
            invoices=[
                Invoice(xml_id="inv1", move_type="out_invoice", partner_xmlid="p1",
                        invoice_date="2025-02-01", lines=[
                            InvoiceLine(product_xmlid="prod_a", qty=2.0, price_unit=100.0, description="Ware A"),
                        ]),
            ],
        )
        with TemporaryDirectory() as tmp:
            module_dir = write_module_dir(spec, Path(tmp))
            findings = validate_module(module_dir)
            errors = [f for f in findings if f.level == "error"]
            self.assertEqual(errors, [], f"Unexpected validation errors: {errors}")
            data_dir = module_dir / "data"
            for name in ("account_chart_data.xml", "purchase_order_data.xml",
                         "stock_warehouse_data.xml", "stock_quant_data.xml",
                         "account_move_data.xml"):
                self.assertTrue((data_dir / name).exists(), f"{name} is missing")
            chart = (data_dir / "account_chart_data.xml").read_text(encoding="utf-8")
            self.assertIn("account.chart.template", chart)
            move_xml = (data_dir / "account_move_data.xml").read_text(encoding="utf-8")
            self.assertIn("allowed_company_ids", move_xml)

    def test_full_accounting_pulls_account_accountant(self):
        spec = self._erp_spec(invoices=[
            Invoice(xml_id="inv1", move_type="out_invoice", partner_xmlid="p1",
                    invoice_date="2025-02-01", lines=[
                        InvoiceLine(product_xmlid="prod_a", qty=1.0, price_unit=100.0, description="x"),
                    ]),
        ])
        self.assertIn("account_accountant", depends(spec))
        spec_invoicing = self._erp_spec(accounting_app="invoicing", invoices=[
            Invoice(xml_id="inv1", move_type="out_invoice", partner_xmlid="p1",
                    invoice_date="2025-02-01", lines=[
                        InvoiceLine(product_xmlid="prod_a", qty=1.0, price_unit=100.0, description="x"),
                    ]),
        ])
        self.assertIn("account", depends(spec_invoicing))
        self.assertNotIn("account_accountant", depends(spec_invoicing))

    def test_validate_flags_unsafe_purchase_state(self):
        with TemporaryDirectory() as tmp:
            module_dir = Path(tmp) / "bt_demo_broken_po"
            data_dir = module_dir / "data"
            data_dir.mkdir(parents=True)
            (module_dir / "__manifest__.py").write_text('{"data": ["data/po.xml"]}', encoding="utf-8")
            (data_dir / "po.xml").write_text(
                '<?xml version="1.0"?><odoo><record id="po1" model="purchase.order">'
                '<field name="state">purchase</field></record></odoo>',
                encoding="utf-8",
            )
            findings = validate_module(module_dir)
            self.assertTrue(any("4.10" in f.message for f in findings))

    def test_validate_flags_account_move_state(self):
        with TemporaryDirectory() as tmp:
            module_dir = Path(tmp) / "bt_demo_broken_am"
            data_dir = module_dir / "data"
            data_dir.mkdir(parents=True)
            (module_dir / "__manifest__.py").write_text('{"data": ["data/am.xml"]}', encoding="utf-8")
            (data_dir / "am.xml").write_text(
                '<?xml version="1.0"?><odoo><record id="am1" model="account.move">'
                '<field name="state">posted</field></record></odoo>',
                encoding="utf-8",
            )
            findings = validate_module(module_dir)
            self.assertTrue(any("4.12" in f.message for f in findings))

    def test_validate_flags_account_move_without_chart(self):
        with TemporaryDirectory() as tmp:
            module_dir = Path(tmp) / "bt_demo_no_chart"
            data_dir = module_dir / "data"
            data_dir.mkdir(parents=True)
            (module_dir / "__manifest__.py").write_text('{"data": ["data/am.xml"]}', encoding="utf-8")
            (data_dir / "am.xml").write_text(
                '<?xml version="1.0"?><odoo><record id="am1" model="account.move">'
                '<field name="move_type">out_invoice</field></record></odoo>',
                encoding="utf-8",
            )
            findings = validate_module(module_dir)
            self.assertTrue(any("try_loading" in f.message for f in findings))

    def test_validate_flags_purchase_without_picking_type(self):
        with TemporaryDirectory() as tmp:
            module_dir = Path(tmp) / "bt_demo_no_picking"
            data_dir = module_dir / "data"
            data_dir.mkdir(parents=True)
            (module_dir / "__manifest__.py").write_text('{"data": ["data/po.xml"]}', encoding="utf-8")
            (data_dir / "po.xml").write_text(
                '<?xml version="1.0"?><odoo><record id="po1" model="purchase.order">'
                '<field name="state">draft</field></record></odoo>',
                encoding="utf-8",
            )
            findings = validate_module(module_dir)
            self.assertTrue(any("picking_type_id" in f.message for f in findings))

    def test_validate_flags_stock_quant_without_warehouse(self):
        with TemporaryDirectory() as tmp:
            module_dir = Path(tmp) / "bt_demo_no_warehouse"
            data_dir = module_dir / "data"
            data_dir.mkdir(parents=True)
            (module_dir / "__manifest__.py").write_text('{"data": ["data/q.xml"]}', encoding="utf-8")
            (data_dir / "q.xml").write_text(
                '<?xml version="1.0"?><odoo><record id="q1" model="stock.quant">'
                '<field name="quantity">5.0</field></record></odoo>',
                encoding="utf-8",
            )
            findings = validate_module(module_dir)
            self.assertTrue(any("stock.warehouse" in f.message for f in findings))


class LanguageTests(unittest.TestCase):
    def _spec(self, country_xmlid="base.ch", language=None, **overrides) -> CustomerSpec:
        base = dict(
            module=Module(technical_name="bt_demo_lang", title="T", summary="S"),
            company=Company(name="Test AG", street="Weg 1", city="Stadt", zip="1",
                            country_xmlid=country_xmlid),
            language=language,
        )
        base.update(overrides)
        return CustomerSpec(**base)

    def test_language_derived_from_country(self):
        self.assertEqual(self._spec("base.ch").resolved_language, "de_CH")
        self.assertEqual(self._spec("base.de").resolved_language, "de_DE")
        self.assertEqual(self._spec("base.us").resolved_language, "en_US")
        # Unknown country falls back to the default language.
        self.assertEqual(self._spec("base.zz").resolved_language, "en_US")

    def test_language_override(self):
        self.assertEqual(self._spec("base.ch", language="en_US").resolved_language, "en_US")

    def test_team_names_follow_language(self):
        self.assertEqual(self._spec(language="en_US").resolved_crm_team_name, "Sales")
        self.assertEqual(self._spec(language="de_CH").resolved_crm_team_name, "Vertrieb")
        self.assertEqual(self._spec(language="en_US").resolved_helpdesk_team_name, "Customer Service")

    def test_records_carry_lang_context(self):
        spec = self._spec(language="de_CH", products=[
            Product(xml_id="p", name="P", type="consu", sale_ok=True, purchase_ok=False,
                    standard_price=5.0),
        ])
        with TemporaryDirectory() as tmp:
            module_dir = write_module_dir(spec, Path(tmp))
            xml = (module_dir / "data" / "product_data.xml").read_text(encoding="utf-8")
            self.assertIn("'lang': 'de_CH'", xml)
            self.assertIn("allowed_company_ids", xml)

    def test_loader_reads_language(self):
        spec = load_spec({
            "module": {"technical_name": "bt_x", "title": "T", "summary": "S"},
            "company": {"name": "N", "street": "s", "city": "c", "zip": "1",
                        "country_xmlid": "base.ch"},
            "language": "en_US",
        })
        self.assertEqual(spec.resolved_language, "en_US")


if __name__ == "__main__":
    unittest.main()

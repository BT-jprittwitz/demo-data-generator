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
    MaintenanceEquipment,
    MaintenanceEquipmentCategory,
    MaintenanceRequest,
    ManufacturingOrder,
    Module,
    Partner,
    Product,
    Project,
    ProjectTask,
    ProjectTaskStage,
    PurchaseOrder,
    PurchaseOrderLine,
    QualityAlert,
    QualityCheck,
    QualityPoint,
    QuotationTemplate,
    QuotationTemplateLine,
    SaleOrder,
    SaleOrderLine,
    SpecError,
    StockQuant,
    Subscription,
    SubscriptionLine,
)
from engine.docker.test_install import analyze_log
from engine.manifest import DEMO_USER_LOGIN, DEMO_USER_PASSWORD, depends, render_hooks_py
from engine.schema import build_schema
from engine.spec_loader import load_spec
from engine.validate import _is_valid_at_uid, _is_valid_de_vat, validate_module

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

    def test_german_chart_template_pulls_l10n_de(self):
        # The localization MUST be declared as a dependency, otherwise
        # account.chart.template._load() installs it mid-load and resets the
        # transaction/registry (verified-patterns.md 4.11).
        for template in ("de_skr03", "de_skr04"):
            spec = self._erp_spec(company=Company(
                name="Test AG", street="Teststrasse 1", city="Teststadt", zip="1234",
                country_xmlid="base.de", chart_template=template,
            ))
            self.assertIn("l10n_de", depends(spec), template)

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


class ProjectAndTemplateTests(unittest.TestCase):
    """sale.order.template ("Angebotsvorlage") and project.project/task/stage."""

    def _spec(self, **overrides) -> CustomerSpec:
        base = dict(
            module=Module(technical_name="bt_demo_proj", title="P", summary="P", description="P"),
            company=Company(name="Test AG", street="Weg 1", city="Stadt", zip="1",
                            country_xmlid="base.de"),
            partners=[
                Partner(xml_id="p1", name="Kunde AG", country_xmlid="base.de",
                        street="Weg 1", city="Stadt", zip="1111", customer_rank=1),
            ],
            products=[
                Product(xml_id="prod_a", name="Ware A", type="consu", sale_ok=True,
                        purchase_ok=True, list_price=100.0),
            ],
        )
        base.update(overrides)
        return CustomerSpec(**base)

    def test_quotation_template_requires_known_product(self):
        with self.assertRaises(SpecError):
            self._spec(quotation_templates=[
                QuotationTemplate(xml_id="t1", name="Paket", lines=[
                    QuotationTemplateLine(product_xmlid="missing"),
                ]),
            ])

    def test_rejects_invalid_task_priority(self):
        with self.assertRaises(SpecError):
            ProjectTask(xml_id="t1", name="Task", project_xmlid="prj", priority="9")

    def test_rejects_invalid_privacy_visibility(self):
        with self.assertRaises(SpecError):
            Project(xml_id="prj", name="Projekt", privacy_visibility="world")

    def test_task_stages_require_a_project(self):
        with self.assertRaises(SpecError):
            self._spec(project_task_stages=[ProjectTaskStage(xml_id="s1", name="Neu")])

    def test_rejects_dangling_task_stage(self):
        with self.assertRaises(SpecError):
            self._spec(
                projects=[Project(xml_id="prj", name="Projekt")],
                project_tasks=[ProjectTask(xml_id="t1", name="Task", project_xmlid="prj",
                                           stage_xmlid="missing")],
            )

    def test_spec_builds_project_and_template_files_and_pulls_project_app(self):
        spec = self._spec(
            quotation_templates=[
                QuotationTemplate(xml_id="tpl1", name="Arbeitsplatz", number_of_days=30,
                                  note="Konditionen", lines=[
                                      QuotationTemplateLine(product_xmlid="prod_a", qty=2.0,
                                                            description="Ware A")]),
            ],
            projects=[Project(xml_id="prj1", name="Projekt A", partner_xmlid="p1",
                              stage_xmlid="project.project_project_stage_1")],
            project_task_stages=[ProjectTaskStage(xml_id="stage1", name="Neu")],
            project_tasks=[ProjectTask(xml_id="task1", name="Aufgabe 1", project_xmlid="prj1",
                                       stage_xmlid="stage1", partner_xmlid="p1", priority="2")],
        )
        self.assertIn("project", depends(spec))
        with TemporaryDirectory() as tmp:
            module_dir = write_module_dir(spec, Path(tmp))
            findings = validate_module(module_dir)
            errors = [f for f in findings if f.level == "error"]
            self.assertEqual(errors, [], f"Unexpected validation errors: {errors}")
            data_dir = module_dir / "data"
            for name in ("sale_order_template_data.xml", "project_task_stage_data.xml",
                         "project_project_data.xml", "project_task_data.xml"):
                self.assertTrue((data_dir / name).exists(), f"{name} is missing")
            template = (data_dir / "sale_order_template_data.xml").read_text(encoding="utf-8")
            self.assertIn("uom.product_uom_unit", template)
            project = (data_dir / "project_project_data.xml").read_text(encoding="utf-8")
            self.assertIn("Command.link(ref('stage1'))", project)

    def test_validate_flags_task_stage_not_linked_to_project(self):
        with TemporaryDirectory() as tmp:
            module_dir = Path(tmp) / "bt_demo_unlinked_stage"
            data_dir = module_dir / "data"
            data_dir.mkdir(parents=True)
            (module_dir / "__manifest__.py").write_text(
                '{"data": ["data/stage.xml", "data/project.xml", "data/task.xml"]}',
                encoding="utf-8",
            )
            (data_dir / "stage.xml").write_text(
                '<?xml version="1.0"?><odoo><record id="s1" model="project.task.type">'
                '<field name="name">Neu</field></record></odoo>',
                encoding="utf-8",
            )
            (data_dir / "project.xml").write_text(
                '<?xml version="1.0"?><odoo><record id="prj" model="project.project">'
                '<field name="name">P</field></record></odoo>',
                encoding="utf-8",
            )
            (data_dir / "task.xml").write_text(
                '<?xml version="1.0"?><odoo><record id="t1" model="project.task">'
                '<field name="name">T</field><field name="project_id" ref="prj"/>'
                '<field name="stage_id" ref="s1"/></record></odoo>',
                encoding="utf-8",
            )
            findings = validate_module(module_dir)
            self.assertTrue(any("type_ids" in f.message for f in findings))

    def test_validate_flags_project_task_without_project(self):
        with TemporaryDirectory() as tmp:
            module_dir = Path(tmp) / "bt_demo_task_no_project"
            data_dir = module_dir / "data"
            data_dir.mkdir(parents=True)
            (module_dir / "__manifest__.py").write_text('{"data": ["data/task.xml"]}', encoding="utf-8")
            (data_dir / "task.xml").write_text(
                '<?xml version="1.0"?><odoo><record id="t1" model="project.task">'
                '<field name="name">T</field></record></odoo>',
                encoding="utf-8",
            )
            findings = validate_module(module_dir)
            self.assertTrue(any("project.project" in f.message for f in findings))


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


class DemoUserTests(unittest.TestCase):
    """Auto-created demo user in the post_init_hook (verified-patterns.md 4.18)."""

    def _hooks(self, **overrides) -> str:
        return render_hooks_py(_minimal_spec(**overrides))

    def test_demo_user_is_created(self):
        hooks = self._hooks()
        self.assertIn("_create_demo_user", hooks)
        self.assertIn(f'"login": "{DEMO_USER_LOGIN}"', hooks)
        self.assertIn(f'"password": "{DEMO_USER_PASSWORD}"', hooks)

    def test_demo_user_name_is_the_company(self):
        self.assertIn('"name": company.name', self._hooks())

    def test_demo_user_copies_admin_groups_and_companies(self):
        hooks = self._hooks()
        self.assertIn("groups = admin.group_ids", hooks)
        self.assertIn("admin.company_ids", hooks)
        self.assertIn('"company_id": company.id', hooks)
        self.assertIn('"company_ids": [Command.set(companies.ids)]', hooks)

    def test_demo_user_creation_skips_existing_login(self):
        # UNIQUE(login): a second demo package must not abort the installation.
        hooks = self._hooks()
        self.assertIn("if existing:", hooks)
        self.assertIn("existing.write", hooks)
        self.assertIn("return", hooks)

    def test_demo_user_does_not_trigger_signup_email(self):
        self.assertIn("no_reset_password=True", self._hooks())


class VatValidationTests(unittest.TestCase):
    """Partner VAT checksum check active with base_vat (verified-patterns.md 4.19)."""

    def _write_partner_module(self, tmp: str, depends: list[str], vat: str) -> Path:
        module_dir = Path(tmp) / "bt_demo_vat"
        data_dir = module_dir / "data"
        data_dir.mkdir(parents=True)
        (module_dir / "__manifest__.py").write_text(
            repr({"depends": depends, "data": ["data/res_partner_data.xml"]}), encoding="utf-8"
        )
        (data_dir / "res_partner_data.xml").write_text(
            '<?xml version="1.0"?><odoo><record id="p1" model="res.partner">'
            f'<field name="vat">{vat}</field></record></odoo>',
            encoding="utf-8",
        )
        return module_dir

    def test_de_vat_checksum_matches_stdnum(self):
        self.assertTrue(_is_valid_de_vat("DE118273454"))
        self.assertTrue(_is_valid_de_vat("DE174829302"))
        self.assertFalse(_is_valid_de_vat("DE118273456"))
        self.assertFalse(_is_valid_de_vat("DE811234567"))

    def test_at_uid_checksum_matches_stdnum(self):
        self.assertTrue(_is_valid_at_uid("ATU22334454"))
        self.assertTrue(_is_valid_at_uid("ATU13585627"))
        self.assertFalse(_is_valid_at_uid("ATU12345678"))

    def test_invalid_german_vat_is_flagged_with_l10n_de(self):
        with TemporaryDirectory() as tmp:
            module_dir = self._write_partner_module(tmp, ["account", "l10n_de"], "DE118273456")
            findings = validate_module(module_dir)
            self.assertTrue(any("4.19" in f.message for f in findings))

    def test_invalid_german_vat_is_not_flagged_without_base_vat(self):
        # l10n_ch does not pull base_vat, so nishcom's VAT is not validated.
        with TemporaryDirectory() as tmp:
            module_dir = self._write_partner_module(tmp, ["account", "l10n_ch"], "DE118273456")
            findings = validate_module(module_dir)
            self.assertFalse(any("4.19" in f.message for f in findings))


class AdjacentProcessTests(unittest.TestCase):
    """Maintenance, quality control, subscriptions and field service
    (verified-patterns.md 4.22-4.26)."""

    def _spec(self, **overrides) -> CustomerSpec:
        base = dict(
            module=Module(technical_name="bt_demo_adj", title="A", summary="A", description="A"),
            company=Company(name="Test AG", street="Weg 1", city="Stadt", zip="1",
                            country_xmlid="base.de"),
            partners=[
                Partner(xml_id="p1", name="Kunde AG", country_xmlid="base.de",
                        street="Weg 1", city="Stadt", zip="1111", customer_rank=1),
            ],
            products=[
                Product(xml_id="comp", name="Teil", type="consu", sale_ok=False,
                        purchase_ok=True, standard_price=5.0),
                Product(xml_id="fin", name="Anlage", type="consu", sale_ok=True,
                        purchase_ok=False, list_price=100.0),
                Product(xml_id="svc", name="Wartung", type="service", sale_ok=True,
                        purchase_ok=False, list_price=10.0, recurring_invoice=True),
            ],
            boms=[Bom(xml_id="bom1", product_xmlid="fin",
                      lines=[BomLine(product_xmlid="comp", qty=2.0)])],
            manufacturing_orders=[ManufacturingOrder(xml_id="mo1", product_xmlid="fin", qty=1.0)],
        )
        base.update(overrides)
        return CustomerSpec(**base)

    def test_rejects_invalid_maintenance_type(self):
        with self.assertRaises(SpecError):
            MaintenanceRequest(xml_id="m1", name="X", maintenance_type="breakdown")

    def test_rejects_move_line_measure_on(self):
        # measure_on='move_line' is forbidden with an mrp operation type.
        with self.assertRaises(SpecError):
            QualityPoint(xml_id="q1", name="Q", measure_on="move_line")

    def test_quality_points_require_mrp(self):
        with self.assertRaises(SpecError):
            self._spec(
                boms=[], manufacturing_orders=[],
                quality_points=[QualityPoint(xml_id="q1", name="Q")],
            )

    def test_rejects_invalid_subscription_plan(self):
        with self.assertRaises(SpecError):
            Subscription(xml_id="s1", partner_xmlid="p1", plan="weekly")

    def test_rejects_dangling_quality_check_production(self):
        with self.assertRaises(SpecError):
            self._spec(
                quality_points=[QualityPoint(xml_id="q1", name="Q")],
                quality_checks=[QualityCheck(xml_id="c1", point_xmlid="q1",
                                             production_xmlid="missing")],
            )

    def test_builds_adjacent_process_files_and_depends(self):
        spec = self._spec(
            maintenance_equipment_categories=[MaintenanceEquipmentCategory(xml_id="cat1", name="Anlagen")],
            maintenance_equipment=[MaintenanceEquipment(xml_id="eq1", name="BHKW 1",
                                                        category_xmlid="cat1", partner_xmlid="p1")],
            maintenance_requests=[MaintenanceRequest(xml_id="mr1", name="Wartung",
                                                     equipment_xmlid="eq1",
                                                     stage_xmlid="maintenance.stage_0")],
            quality_points=[QualityPoint(xml_id="qp1", name="QCP-1", product_xmlids=["fin"],
                                         test_type="passfail")],
            quality_checks=[QualityCheck(xml_id="qc1", point_xmlid="qp1",
                                         production_xmlid="mo1", product_xmlid="fin",
                                         quality_state="pass")],
            quality_alerts=[QualityAlert(xml_id="qa1", name="Abweichung",
                                         product_xmlid="fin", partner_xmlid="p1")],
            subscriptions=[Subscription(xml_id="sub1", partner_xmlid="p1", plan="month",
                                        lines=[SubscriptionLine(product_xmlid="svc", qty=1.0)])],
            projects=[Project(xml_id="prj_fsm", name="Einsätze", is_fsm=True)],
            project_tasks=[ProjectTask(xml_id="ft1", name="Einsatz", project_xmlid="prj_fsm",
                                       partner_xmlid="p1")],
        )
        deps = depends(spec)
        for app in ("maintenance", "quality_control", "sale_subscription", "industry_fsm"):
            self.assertIn(app, deps)
        with TemporaryDirectory() as tmp:
            module_dir = write_module_dir(spec, Path(tmp))
            findings = validate_module(module_dir)
            errors = [f for f in findings if f.level == "error"]
            self.assertEqual(errors, [], f"Unexpected validation errors: {errors}")
            data_dir = module_dir / "data"
            for name in ("maintenance_team_data.xml", "maintenance_equipment_category_data.xml",
                         "maintenance_equipment_data.xml", "maintenance_request_data.xml",
                         "quality_point_data.xml", "quality_check_data.xml",
                         "quality_alert_data.xml", "sale_order_subscription_data.xml"):
                self.assertTrue((data_dir / name).exists(), f"{name} is missing")
            project = (data_dir / "project_project_data.xml").read_text(encoding="utf-8")
            self.assertIn("is_fsm", project)
            self.assertNotIn("type_ids", project.split("prj_fsm")[1])
            products = (data_dir / "product_data.xml").read_text(encoding="utf-8")
            self.assertIn("recurring_invoice", products)

    def test_rejects_recurring_product_on_non_draft_order(self):
        # sale_subscription._constraint_subscription_plan would abort the install.
        with self.assertRaises(SpecError):
            self._spec(example_orders=[
                SaleOrder(xml_id="so1", partner_xmlid="p1", state="sent", lines=[
                    SaleOrderLine(product_xmlid="svc", qty=1.0, description="Wartung"),
                ]),
            ])

    def test_enertec_example_parses_new_sections(self):
        spec = load_spec(json.loads(
            (REPO_ROOT / "examples" / "enertec_kraftwerke.json").read_text(encoding="utf-8")
        ))
        self.assertTrue(spec.needs_maintenance)
        self.assertTrue(spec.needs_quality)
        self.assertTrue(spec.needs_subscriptions)
        self.assertTrue(spec.needs_field_service)
        self.assertTrue(any(p.recurring_invoice for p in spec.products))

    def test_validate_flags_recurring_invoice_without_subscription(self):
        with TemporaryDirectory() as tmp:
            module_dir = Path(tmp) / "bt_demo_recurring"
            data_dir = module_dir / "data"
            data_dir.mkdir(parents=True)
            (module_dir / "__manifest__.py").write_text(
                '{"depends": ["sale_management"], "data": ["data/product_data.xml"]}',
                encoding="utf-8",
            )
            (data_dir / "product_data.xml").write_text(
                '<?xml version="1.0"?><odoo><record id="p1" model="product.product">'
                '<field name="name">P</field><field name="recurring_invoice">True</field>'
                "</record></odoo>",
                encoding="utf-8",
            )
            findings = validate_module(module_dir)
            self.assertTrue(any("4.25" in f.message for f in findings))


class InstallLogTests(unittest.TestCase):
    """Pure log analysis of the installation smoke test (engine/docker/test_install.py)."""

    def test_success_log(self):
        log = "INFO loading bt_demo_x\nModule bt_demo_x loaded in 1.19s, 3790 queries\n"
        ok, reasons = analyze_log(log, "bt_demo_x")
        self.assertTrue(ok, reasons)
        self.assertEqual(reasons, [])

    def test_traceback_is_failure(self):
        log = "Module bt_demo_x loaded in 1.0s\nTraceback (most recent call last):\n..."
        ok, reasons = analyze_log(log, "bt_demo_x")
        self.assertFalse(ok)
        self.assertTrue(any("Traceback" in r for r in reasons))

    def test_critical_is_failure(self):
        log = "Module bt_demo_x loaded in 1.0s\nCRITICAL something\n"
        ok, reasons = analyze_log(log, "bt_demo_x")
        self.assertFalse(ok)
        self.assertTrue(any("CRITICAL" in r for r in reasons))

    def test_missing_marker_is_failure(self):
        log = "INFO loading bt_demo_x\n"
        ok, reasons = analyze_log(log, "bt_demo_x")
        self.assertFalse(ok)
        self.assertTrue(any("success marker" in r for r in reasons))

    def test_marker_of_another_module_does_not_count(self):
        log = "Module bt_other loaded in 1.0s\n"
        ok, _ = analyze_log(log, "bt_demo_x")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()

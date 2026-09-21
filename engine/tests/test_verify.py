"""Tests for the spec-aware Postgres assertions of the install smoke test."""
from __future__ import annotations

import unittest

from engine.model import (
    Company,
    CustomerSpec,
    Invoice,
    InvoiceLine,
    Module,
    Partner,
    Product,
    Project,
    ProjectTask,
    ProjectTaskStage,
    QuotationTemplate,
    QuotationTemplateLine,
    SaleOrder,
    SaleOrderLine,
)
from engine.verify import company_id_query, data_checks, standard_price_check


def _spec(**overrides) -> CustomerSpec:
    base = dict(
        module=Module(technical_name="bt_demo_v", title="V", summary="V", description="V"),
        company=Company(name="Test AG", street="Weg 1", city="Stadt", zip="1",
                        country_xmlid="base.ch"),
        partners=[
            Partner(xml_id="p1", name="Kunde AG", country_xmlid="base.ch",
                    street="Weg 1", city="Stadt", zip="1111", customer_rank=1),
        ],
        products=[
            Product(xml_id="prod_a", name="Ware A", type="consu", sale_ok=True,
                    purchase_ok=True, list_price=100.0, standard_price=40.0),
            Product(xml_id="prod_b", name="Ware B", type="consu", sale_ok=True,
                    purchase_ok=True, list_price=50.0),
        ],
    )
    base.update(overrides)
    return CustomerSpec(**base)


def _labels(checks) -> dict[str, object]:
    return {c.label: c.expected for c in checks}


class DataChecksTests(unittest.TestCase):
    def test_company_is_always_checked(self):
        checks = data_checks(_spec())
        self.assertEqual(_labels(checks)["company"], 1)

    def test_empty_sections_are_skipped(self):
        labels = _labels(data_checks(_spec(partners=[])))
        for absent in ("partners", "invoices", "projects", "crm_leads", "quotation_templates"):
            self.assertNotIn(absent, labels)

    def test_counts_follow_the_spec(self):
        spec = _spec(
            partners=[
                Partner(xml_id="p1", name="Kunde AG", country_xmlid="base.ch",
                        street="Weg 1", city="Stadt", zip="1111", customer_rank=1),
                Partner(xml_id="p2", name="Kunde 2 AG", country_xmlid="base.ch",
                        street="Weg 2", city="Stadt", zip="2222", customer_rank=1),
            ],
            quotation=SaleOrder(xml_id="q1", partner_xmlid="p1", lines=[
                SaleOrderLine(product_xmlid="prod_a", qty=1.0, description="x"),
            ]),
            crm_leads=[],
        )
        labels = _labels(data_checks(spec))
        self.assertEqual(labels["partners"], 2)
        self.assertEqual(labels["products"], 2)
        self.assertEqual(labels["sale_orders"], 1)

    def test_quotation_and_example_orders_are_summed(self):
        spec = _spec(
            quotation=SaleOrder(xml_id="q1", partner_xmlid="p1", lines=[]),
            example_orders=[SaleOrder(xml_id="e1", partner_xmlid="p1", lines=[])],
        )
        self.assertEqual(_labels(data_checks(spec))["sale_orders"], 2)

    def test_invoice_posting_is_checked_separately(self):
        spec = _spec(invoices=[
            Invoice(xml_id="inv1", move_type="out_invoice", partner_xmlid="p1",
                    invoice_date="2025-01-01", lines=[
                        InvoiceLine(product_xmlid="prod_a", qty=1.0, price_unit=1.0, description="x"),
                    ]),
        ])
        labels = _labels(data_checks(spec))
        self.assertEqual(labels["invoices"], 1)
        self.assertEqual(labels["invoices_posted"], 1)
        posted = next(c for c in data_checks(spec) if c.label == "invoices_posted")
        self.assertIn("state = 'posted'", posted.sql)

    def test_project_checks(self):
        spec = _spec(
            projects=[Project(xml_id="prj", name="P")],
            project_task_stages=[ProjectTaskStage(xml_id="s1", name="Neu")],
            project_tasks=[
                ProjectTask(xml_id="t1", name="T1", project_xmlid="prj", stage_xmlid="s1"),
                ProjectTask(xml_id="t2", name="T2", project_xmlid="prj"),
            ],
            quotation_templates=[
                QuotationTemplate(xml_id="tpl", name="Paket", lines=[
                    QuotationTemplateLine(product_xmlid="prod_a"),
                ]),
            ],
        )
        labels = _labels(data_checks(spec))
        self.assertEqual(labels["projects"], 1)
        self.assertEqual(labels["project_task_stages"], 1)
        self.assertEqual(labels["project_tasks"], 2)
        self.assertEqual(labels["project_tasks_with_declared_stage"], 1)
        self.assertEqual(labels["quotation_templates"], 1)


class StandardPriceCheckTests(unittest.TestCase):
    def test_none_without_standard_price(self):
        spec = _spec(products=[
            Product(xml_id="prod_a", name="Ware A", type="consu", sale_ok=True,
                    purchase_ok=True, list_price=100.0),
        ])
        self.assertIsNone(standard_price_check(spec, 2))

    def test_counts_products_with_standard_price(self):
        check = standard_price_check(_spec(), 7)
        self.assertIsNotNone(check)
        self.assertEqual(check.expected, 1)
        self.assertIn("standard_price ? '7'", check.sql)


class CompanyIdQueryTests(unittest.TestCase):
    def test_uses_module_and_company_xmlid(self):
        sql = company_id_query(_spec())
        self.assertIn("module = 'bt_demo_v'", sql)
        self.assertIn("name = 'demo_company'", sql)
        self.assertIn("model = 'res.company'", sql)


if __name__ == "__main__":
    unittest.main()

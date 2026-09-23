"""Tests for the token-saving spec features: compact tables, the optional
customer_profile and the relatability guardrail (engine/spec_loader.py,
engine/validate.py, engine/bundles.py)."""
from __future__ import annotations

import contextlib
import io
import json
import unittest

from engine.bundles import capabilities_data
from engine.cli import main
from engine.model import SpecError
from engine.spec_loader import load_spec
from engine.validate import check_spec_relatability


def _spec(**overrides) -> dict:
    spec = {
        "module": {"technical_name": "bt_x", "title": "T", "summary": "S"},
        "company": {"name": "N", "street": "Weg 1", "city": "Stadt", "zip": "1",
                    "country_xmlid": "base.ch"},
    }
    spec.update(overrides)
    return spec


class CompactTableTests(unittest.TestCase):
    def test_table_records_parse(self):
        spec = load_spec(_spec(partners=[
            ["xml_id", "name", "country_xmlid", "street", "city", "zip"],
            ["p_c1", "Autohaus Vogel GmbH", "base.de", "Karlstrasse 100", "Karlsruhe", "76133"],
            ["p_c2", "Brauerei Durlacher GmbH", "base.de", "Allee 12", "Karlsruhe", "76131"],
        ]))
        self.assertEqual(len(spec.partners), 2)
        self.assertEqual(spec.partners[0].name, "Autohaus Vogel GmbH")
        self.assertEqual(spec.partners[1].city, "Karlsruhe")

    def test_nested_lines_table_parses(self):
        spec = load_spec(_spec(
            partners=[["xml_id", "name", "country_xmlid", "street", "city", "zip"],
                      ["p_c1", "Kunde", "base.ch", "Weg 1", "Stadt", "1"]],
            products=[["xml_id", "name", "type", "sale_ok", "purchase_ok"],
                      ["prod_a", "Produkt A", "consu", True, False]],
            example_orders=[
                {"xml_id": "so1", "partner_xmlid": "p_c1", "state": "sent",
                 "lines": [["product_xmlid", "qty", "description"],
                           ["prod_a", 2.0, "zwei Stueck"]]},
            ],
        ))
        self.assertEqual(spec.example_orders[0].lines[0].product_xmlid, "prod_a")
        self.assertEqual(spec.example_orders[0].lines[0].qty, 2.0)

    def test_table_row_length_mismatch_is_rejected(self):
        with self.assertRaises(SpecError):
            load_spec(_spec(partners=[
                ["xml_id", "name"],
                ["p_c1", "Name", "extra"],
            ]))

    def test_table_header_unknown_field_is_rejected(self):
        with self.assertRaises(SpecError):
            load_spec(_spec(partners=[
                ["xml_id", "nope"],
                ["p_c1", "x"],
            ]))

    def test_verbose_records_still_work(self):
        spec = load_spec(_spec(partners=[
            {"xml_id": "p_c1", "name": "Kunde", "country_xmlid": "base.ch",
             "street": "Weg 1", "city": "Stadt", "zip": "1"},
        ]))
        self.assertEqual(spec.partners[0].name, "Kunde")


class CustomerProfileTests(unittest.TestCase):
    def test_profile_parses(self):
        spec = load_spec(_spec(customer_profile={
            "industry": "Werbemittelhandel",
            "business_model": "B2B Full-Service",
            "product_domains": ["Textilien", "Trinkflaschen"],
            "customer_segments": ["Mittelstand"],
            "region": "Karlsruhe",
        }))
        self.assertIsNotNone(spec.customer_profile)
        self.assertEqual(spec.customer_profile.industry, "Werbemittelhandel")
        self.assertEqual(spec.customer_profile.product_domains, ["Textilien", "Trinkflaschen"])

    def test_unknown_profile_field_is_rejected(self):
        with self.assertRaises(SpecError):
            load_spec(_spec(customer_profile={"industry": "x", "nope": 1}))

    def test_absent_profile_is_none(self):
        self.assertIsNone(load_spec(_spec()).customer_profile)


class RelatabilityTests(unittest.TestCase):
    def test_placeholder_is_an_error(self):
        findings = check_spec_relatability(
            load_spec(_spec(module={"technical_name": "bt_x", "title": "T",
                                    "summary": "TODO: one sentence."}))
        )
        errors = [f for f in findings if f.level == "error"]
        self.assertTrue(errors)
        self.assertTrue(any("TODO" in f.message for f in errors))

    def test_generic_catalog_warns(self):
        spec = load_spec(_spec(
            customer_profile={"product_domains": ["Textilien", "Trinkflaschen"]},
            products=[["xml_id", "name", "type", "sale_ok", "purchase_ok"],
                      ["p1", "Softwarelizenz", "service", True, False]],
        ))
        findings = check_spec_relatability(spec)
        self.assertTrue(any(f.level == "warning" and "product_domains" in f.message
                            for f in findings))

    def test_matching_catalog_does_not_warn(self):
        spec = load_spec(_spec(
            customer_profile={"product_domains": ["Textilien", "Trinkflaschen"]},
            products=[["xml_id", "name", "type", "sale_ok", "purchase_ok"],
                      ["p1", "T-Shirt aus Textilien", "consu", True, False]],
        ))
        findings = check_spec_relatability(spec)
        self.assertFalse([f for f in findings if f.level == "warning"])

    def test_no_profile_no_findings(self):
        self.assertEqual(check_spec_relatability(load_spec(_spec())), [])


class CapabilitiesJsonTests(unittest.TestCase):
    def test_capabilities_data_shape(self):
        data = capabilities_data()
        ids = {b["id"] for b in data}
        self.assertIn("mrp", ids)
        mrp = next(b for b in data if b["id"] == "mrp")
        self.assertEqual(mrp["requires"], ["stock", "products"])
        self.assertEqual(mrp["apps"], ["mrp"])

    def test_capabilities_cli_json_is_valid(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            rc = main(["capabilities", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(any(b["id"] == "sales" for b in payload["bundles"]))


if __name__ == "__main__":
    unittest.main()

"""Tests for the spec scaffold (engine/scaffold.py, engine.cli new)."""
from __future__ import annotations

import json
import unittest

from engine.bundles import BundleError
from engine.scaffold import build_skeleton, default_technical_name, normalize_country, to_json
from engine.spec_loader import load_spec


class ScaffoldTests(unittest.TestCase):
    def test_country_normalization(self) -> None:
        self.assertEqual(normalize_country("ch"), "base.ch")
        self.assertEqual(normalize_country("base.de"), "base.de")

    def test_technical_name(self) -> None:
        self.assertEqual(default_technical_name("Muster Foerdertechnik AG"), "bt_demo_muster_foerdertechnik_ag")
        self.assertEqual(default_technical_name("Nishcom AG"), "bt_demo_nishcom_ag")

    def test_skeleton_contains_resolved_sections(self) -> None:
        skeleton = build_skeleton(["mrp", "sales"], name="Muster AG", country="ch")
        for key in ("partners", "products", "boms", "manufacturing_orders", "stock_quants",
                    "quotation", "example_orders"):
            self.assertIn(key, skeleton)
        self.assertIsNone(skeleton["quotation"])
        self.assertEqual(skeleton["boms"], [])

    def test_skeleton_is_loadable(self) -> None:
        skeleton = build_skeleton(["mrp", "sales", "accounting"], name="Muster AG", country="ch")
        spec = load_spec(skeleton)  # must not raise
        self.assertEqual(spec.company.name, "Muster AG")
        self.assertIn("manufacturing_orders", skeleton)

    def test_unknown_bundle_raises(self) -> None:
        with self.assertRaises(BundleError):
            build_skeleton(["nope"], name="X", country="ch")

    def test_output_is_valid_json(self) -> None:
        skeleton = build_skeleton(["sales"], name="Muster AG", country="ch")
        self.assertEqual(json.loads(to_json(skeleton)), skeleton)


if __name__ == "__main__":
    unittest.main()

"""Tests for the capability-bundle catalog (engine/bundles.py)."""
from __future__ import annotations

import dataclasses
import unittest
from pathlib import Path

from engine.bundles import (
    BUNDLES,
    SECTION_ORDER,
    Bundle,
    BundleError,
    resolve,
    render_capabilities_markdown,
    validate_bundles,
)
from engine.model import CustomerSpec

REFERENCE = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "odoo-demo-data"
    / "reference"
    / "capabilities.md"
)


class BundleCatalogTests(unittest.TestCase):
    def test_catalog_is_valid(self) -> None:
        self.assertEqual(validate_bundles(), [])

    def test_every_section_is_a_spec_field(self) -> None:
        spec_fields = {f.name for f in dataclasses.fields(CustomerSpec)}
        for bundle in BUNDLES.values():
            for section in bundle.sections:
                self.assertIn(section, spec_fields, f"{bundle.id}: {section}")
                self.assertIn(section, SECTION_ORDER, f"{bundle.id}: {section}")

    def test_no_section_is_claimed_by_two_bundles(self) -> None:
        seen: dict[str, str] = {}
        for bundle in BUNDLES.values():
            for section in bundle.sections:
                self.assertNotIn(section, seen, f"{section} in {seen.get(section)} and {bundle.id}")
                seen[section] = bundle.id


class ResolveTests(unittest.TestCase):
    def test_mrp_pulls_stock_and_products(self) -> None:
        resolved = resolve(["mrp"])
        self.assertEqual(set(resolved.bundle_ids), {"mrp", "stock", "products"})
        self.assertEqual(resolved.sections, ("products", "boms", "manufacturing_orders", "stock_quants"))
        self.assertIn("mrp", resolved.apps)
        self.assertIn("stock", resolved.apps)

    def test_purchase_pulls_stock(self) -> None:
        resolved = resolve(["purchase"])
        self.assertIn("stock", resolved.bundle_ids)

    def test_unknown_bundle_raises(self) -> None:
        with self.assertRaises(BundleError):
            resolve(["does_not_exist"])

    def test_cycle_is_detected(self) -> None:
        cyclic = {
            "a": Bundle(id="a", label="A", requires=("b",)),
            "b": Bundle(id="b", label="B", requires=("a",)),
        }
        with self.assertRaises(BundleError):
            resolve(["a"], cyclic)
        self.assertTrue(validate_bundles(cyclic))


class CapabilitiesReferenceTests(unittest.TestCase):
    def test_reference_is_in_sync_with_catalog(self) -> None:
        self.assertTrue(REFERENCE.exists(), f"missing generated reference: {REFERENCE}")
        self.assertEqual(
            REFERENCE.read_text(encoding="utf-8"),
            render_capabilities_markdown(),
            "skills/odoo-demo-data/reference/capabilities.md is stale - regenerate "
            "with: python3 -m engine.cli capabilities --out "
            "skills/odoo-demo-data/reference/capabilities.md",
        )


if __name__ == "__main__":
    unittest.main()

"""Production is only possible against a currently approved recipe (3.2)."""

import frappe

from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.tests import fixtures


class TestWorkOrderRecipeGuard(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		cls.kg = fixtures.ensure_uom("Kg")

	def setUp(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		self.blend = fixtures.ensure_item("Guard Blend", nature="Bulk Blend")
		self.chilli = fixtures.ensure_item("Chilli Powder", nature="Raw Material")
		self.cumin = fixtures.ensure_item("Cumin Powder", nature="Raw Material")

	def tearDown(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()

	def make_recipe(self, chilli_pct=60, submit=True):
		doc = frappe.get_doc(
			{
				"doctype": "FM Recipe",
				"item": self.blend,
				"company": self.site["company"],
				"batch_size": 100,
				"batch_uom": self.kg,
				"ingredients": [
					{"item_code": self.chilli, "percentage": chilli_pct, "uom": self.kg},
					{"item_code": self.cumin, "percentage": 100 - chilli_pct, "uom": self.kg},
				],
			}
		)
		doc.insert()
		if submit:
			doc.submit()

		return doc

	def make_work_order(self, bom_no, qty=10):
		"""Insert a draft Work Order.

		Inserted rather than validated in isolation: ERPNext's own
		``reset_use_multi_level_bom`` assumes the normal document lifecycle, so
		calling ``validate`` on an unsaved doc fails for reasons unrelated to
		this app. A draft insert runs our hook through the real path.
		"""
		doc = frappe.get_doc(
			{
				"doctype": "Work Order",
				"production_item": self.blend,
				"bom_no": bom_no,
				"qty": qty,
				"company": self.site["company"],
				"fg_warehouse": self.site["stores"],
				"wip_warehouse": self.site["stores"],
				"source_warehouse": self.site["stores"],
				"use_multi_level_bom": 0,
			}
		)
		doc.insert()
		return doc

	def test_approved_recipe_can_be_produced(self):
		recipe = self.make_recipe()
		self.make_work_order(recipe.bom)  # must not raise

	def test_superseded_recipe_cannot_be_produced(self):
		"""The old BOM survives for history, but may not start new production."""
		first = self.make_recipe(chilli_pct=60)
		old_bom = first.bom
		self.make_recipe(chilli_pct=50)

		first.reload()
		self.assertEqual(first.status, "Superseded")

		with self.assertRaises(frappe.ValidationError):
			self.make_work_order(old_bom)

	def test_newest_revision_can_be_produced(self):
		self.make_recipe(chilli_pct=60)
		second = self.make_recipe(chilli_pct=50)
		self.make_work_order(second.bom)  # must not raise

	def test_bom_without_a_recipe_is_left_alone(self):
		"""This app does not take over every BOM on the site."""
		bom = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": self.blend,
				"company": self.site["company"],
				"quantity": 100,
				"uom": self.kg,
				"currency": frappe.get_cached_value(
					"Company", self.site["company"], "default_currency"
				),
				"is_active": 1,
				"is_default": 1,
				"items": [{"item_code": self.chilli, "qty": 100, "uom": self.kg}],
			}
		)
		bom.insert()
		bom.submit()

		self.assertFalse(bom.fm_recipe)
		self.make_work_order(bom.name)  # must not raise

	def test_work_order_without_a_bom_is_left_alone(self):
		from food_manufacturing.overrides.work_order import validate_recipe_approved

		validate_recipe_approved(frappe._dict({"bom_no": None}))  # must not raise

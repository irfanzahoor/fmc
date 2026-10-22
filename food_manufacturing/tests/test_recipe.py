"""FM Recipe: percentages, UOM conversion, approval and BOM generation."""

import frappe
from frappe.utils import flt

from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.food_manufacturing_recipe.doctype.fm_recipe.fm_recipe import (
	get_approved_recipe,
)
from food_manufacturing.tests import fixtures


class TestFMRecipe(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		cls.kg = fixtures.ensure_uom("Kg")
		cls.gram = fixtures.ensure_uom("Gram")
		fixtures.ensure_uom_conversion(cls.kg, cls.gram, 1000)

	def setUp(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		self.blend = fixtures.ensure_item("Masala Blend", nature="Bulk Blend")
		self.chilli = fixtures.ensure_item("Chilli Powder", nature="Raw Material")
		self.cumin = fixtures.ensure_item("Cumin Powder", nature="Raw Material")

	def tearDown(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()

	def make_recipe(self, ingredients=None, submit=False, **overrides):
		values = {
			"doctype": "FM Recipe",
			"item": self.blend,
			"company": self.site["company"],
			"batch_size": 100,
			"batch_uom": self.kg,
			# `is not None`, so that an explicitly empty formula is not
			# silently replaced by the default one.
			"ingredients": ingredients
			if ingredients is not None
			else [
				{"item_code": self.chilli, "percentage": 60, "uom": self.kg},
				{"item_code": self.cumin, "percentage": 40, "uom": self.kg},
			],
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert()
		if submit:
			doc.submit()

		return doc

	# -- 3.1 percentages and conversion --------------------------------------

	def test_percentages_must_total_one_hundred(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_recipe(
				ingredients=[
					{"item_code": self.chilli, "percentage": 60, "uom": self.kg},
					{"item_code": self.cumin, "percentage": 30, "uom": self.kg},
				]
			)

	def test_percentages_over_one_hundred_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_recipe(
				ingredients=[
					{"item_code": self.chilli, "percentage": 70, "uom": self.kg},
					{"item_code": self.cumin, "percentage": 40, "uom": self.kg},
				]
			)

	def test_quantities_derived_from_percentages(self):
		doc = self.make_recipe()
		self.assertEqual(flt(doc.total_percentage), 100)
		by_item = {row.item_code: row for row in doc.ingredients}
		self.assertEqual(flt(by_item[self.chilli].qty), 60)
		self.assertEqual(flt(by_item[self.cumin].qty), 40)

	def test_uom_conversion_is_explicit(self):
		"""An ingredient entered in grams gets a stored conversion factor."""
		doc = self.make_recipe(
			ingredients=[
				{"item_code": self.chilli, "percentage": 60, "uom": self.gram},
				{"item_code": self.cumin, "percentage": 40, "uom": self.kg},
			]
		)
		by_item = {row.item_code: row for row in doc.ingredients}
		# 60% of 100 Kg = 60 Kg = 60,000 g
		self.assertEqual(flt(by_item[self.chilli].conversion_factor), 1000)
		self.assertEqual(flt(by_item[self.chilli].qty), 60000)

	def test_missing_uom_conversion_is_reported(self):
		exotic = fixtures.ensure_uom("_FMT Exotic Unit")
		with self.assertRaises(frappe.ValidationError):
			self.make_recipe(
				ingredients=[
					{"item_code": self.chilli, "percentage": 60, "uom": exotic},
					{"item_code": self.cumin, "percentage": 40, "uom": self.kg},
				]
			)

	def test_batch_size_must_be_positive(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_recipe(batch_size=0)

	def test_duplicate_ingredient_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_recipe(
				ingredients=[
					{"item_code": self.chilli, "percentage": 50, "uom": self.kg},
					{"item_code": self.chilli, "percentage": 50, "uom": self.kg},
				]
			)

	def test_recipe_cannot_contain_its_own_output(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_recipe(
				ingredients=[
					{"item_code": self.blend, "percentage": 50, "uom": self.kg},
					{"item_code": self.cumin, "percentage": 50, "uom": self.kg},
				]
			)

	def test_output_item_must_be_a_bulk_blend(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_recipe(item=self.chilli)

	def test_empty_formula_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_recipe(ingredients=[])

	# -- 3.3 BOM generation ---------------------------------------------------

	def test_approval_generates_a_submitted_bom(self):
		doc = self.make_recipe(submit=True)
		self.assertEqual(doc.status, "Approved")
		self.assertTrue(doc.bom)

		bom = frappe.get_doc("BOM", doc.bom)
		self.assertEqual(bom.docstatus, 1)
		self.assertEqual(bom.item, self.blend)
		self.assertEqual(flt(bom.quantity), 100)
		self.assertEqual(bom.fm_recipe, doc.name)

		bom_qty = {row.item_code: flt(row.qty) for row in bom.items}
		self.assertEqual(bom_qty, {self.chilli: 60, self.cumin: 40})

	def test_get_approved_recipe(self):
		self.assertIsNone(get_approved_recipe(self.blend, self.site["company"]))
		doc = self.make_recipe(submit=True)
		self.assertEqual(get_approved_recipe(self.blend, self.site["company"]), doc.name)

	# -- 3.4 revisions preserve history --------------------------------------

	def test_revision_increments_per_item(self):
		first = self.make_recipe(submit=True)
		second = self.make_recipe(
			ingredients=[
				{"item_code": self.chilli, "percentage": 50, "uom": self.kg},
				{"item_code": self.cumin, "percentage": 50, "uom": self.kg},
			],
			submit=True,
		)
		self.assertEqual(first.revision, 1)
		self.assertEqual(second.revision, 2)

	def test_new_revision_supersedes_the_old_one_without_touching_its_bom(self):
		first = self.make_recipe(submit=True)
		first_bom = first.bom
		first_bom_items = {
			row.item_code: flt(row.qty) for row in frappe.get_doc("BOM", first_bom).items
		}

		second = self.make_recipe(
			ingredients=[
				{"item_code": self.chilli, "percentage": 50, "uom": self.kg},
				{"item_code": self.cumin, "percentage": 50, "uom": self.kg},
			],
			submit=True,
		)

		first.reload()
		self.assertEqual(first.status, "Superseded")
		self.assertEqual(second.status, "Approved")
		self.assertEqual(second.supersedes, first.name)

		# The old BOM is untouched, still submitted, and still its own revision.
		self.assertNotEqual(second.bom, first_bom)
		old_bom = frappe.get_doc("BOM", first_bom)
		self.assertEqual(old_bom.docstatus, 1)
		self.assertEqual(
			{row.item_code: flt(row.qty) for row in old_bom.items}, first_bom_items
		)

	def test_cancelling_a_revision_restores_the_previous_one(self):
		first = self.make_recipe(submit=True)
		second = self.make_recipe(
			ingredients=[
				{"item_code": self.chilli, "percentage": 50, "uom": self.kg},
				{"item_code": self.cumin, "percentage": 50, "uom": self.kg},
			],
			submit=True,
		)

		second.cancel()
		first.reload()
		self.assertEqual(first.status, "Approved")
		self.assertEqual(get_approved_recipe(self.blend, self.site["company"]), first.name)

	def test_cancelling_cancels_the_generated_bom(self):
		doc = self.make_recipe(submit=True)
		bom = doc.bom
		doc.cancel()
		self.assertEqual(frappe.db.get_value("BOM", bom, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value("FM Recipe", doc.name, "status"), "Cancelled")

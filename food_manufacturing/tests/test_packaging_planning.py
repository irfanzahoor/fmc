"""Acceptance examples for packaging material planning.

The brief's worked example: **50 kg produces 1,000 packs of 50 g before any
loss allowance.** Everything below is checked against that.
"""

import frappe
from frappe.utils import flt

from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.packaging.planning import plan
from food_manufacturing.packaging.requests import create_material_request
from food_manufacturing.tests import fixtures

KG = "Kg"
GRAM = "Gram"
NOS = "Nos"
PACKS = 1000
FILL_G = 50.0


class TestPackagingPlanning(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		fixtures.ensure_uom(KG)
		fixtures.ensure_uom(GRAM)
		# ERPNext ships Kg -> Gram = 1000 and refuses the inverse row, so the
		# planner has to read the conversion backwards. Nothing is seeded here;
		# that it works off the shipped row is part of what is being tested.

	def setUp(self):
		fixtures.cleanup_requests()
		fixtures.cleanup()
		fixtures.cleanup_users()

		self.tag = self._testMethodName.replace("test_", "")[:14]
		self.policy = fixtures.ensure_policy(self.site, packing_loss_percent=0)

		self.blend = fixtures.ensure_item(
			f"APlanBlend {self.tag}", nature="Bulk Blend", has_batch=False
		)
		self.pouch = fixtures.ensure_item(
			f"APlanPouch {self.tag}", nature="Packaging Material", has_batch=False, uom=NOS
		)
		self.label = fixtures.ensure_item(
			f"APlanLabel {self.tag}", nature="Packaging Material", has_batch=False, uom=NOS
		)
		self.sku = fixtures.ensure_item(
			f"APlanSKU {self.tag}", nature="Finished Good", has_batch=False, uom=NOS
		)

		# The pack is filled in grams; the blend lives in kilograms.
		frappe.db.set_value("Item", self.sku, {
			"fm_bulk_item": self.blend,
			"fm_pack_size": FILL_G,
			"fm_pack_uom": GRAM,
		})
		frappe.clear_document_cache("Item", self.sku)

		self.bom = self.packaging_bom()

	def tearDown(self):
		frappe.set_user("Administrator")
		fixtures.cleanup_requests()
		fixtures.cleanup()
		fixtures.cleanup_users()

	def packaging_bom(self):
		"""One pouch and one label per pack, plus the blend it is filled with."""
		doc = frappe.get_doc({
			"doctype": "BOM",
			"item": self.sku,
			"company": self.site["company"],
			"quantity": 1,
			"is_active": 1,
			"is_default": 1,
			"items": [
				{"item_code": self.blend, "qty": 0.05, "uom": KG},
				{"item_code": self.pouch, "qty": 1, "uom": NOS},
				{"item_code": self.label, "qty": 1, "uom": NOS},
			],
		})
		doc.insert()
		doc.submit()
		return doc.name

	def receive(self, item_code, qty, rate=10):
		doc = frappe.get_doc({
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"purpose": "Material Receipt",
			"company": self.site["company"],
			"items": [{
				"item_code": item_code, "qty": qty,
				"t_warehouse": self.site["stores"], "basic_rate": rate,
			}],
		})
		doc.insert()
		doc.submit()
		return doc

	def line(self, result, item_code):
		return next(row for row in result["lines"] if row["item_code"] == item_code)

	# --- the worked example -------------------------------------------------

	def test_1000_packs_of_50g_need_50kg_of_blend(self):
		result = plan(self.site["company"], [{"item_code": self.sku, "qty": PACKS}])

		blend = self.line(result, self.blend)
		self.assertAlmostEqual(blend["required_qty"], 50.0, places=4)
		self.assertEqual(blend["uom"], KG)

	def test_the_gram_to_kilogram_conversion_is_reported(self):
		result = plan(self.site["company"], [{"item_code": self.sku, "qty": PACKS}])

		conversion = self.line(result, self.blend)["conversion"]
		self.assertEqual(conversion["from_qty"], FILL_G)
		self.assertEqual(conversion["from_uom"], GRAM)
		self.assertEqual(conversion["to_uom"], KG)
		self.assertAlmostEqual(conversion["factor"], 0.001, places=6)

	def test_one_pouch_and_one_label_per_pack(self):
		result = plan(self.site["company"], [{"item_code": self.sku, "qty": PACKS}])

		self.assertAlmostEqual(self.line(result, self.pouch)["required_qty"], 1000.0, places=2)
		self.assertAlmostEqual(self.line(result, self.label)["required_qty"], 1000.0, places=2)

	def test_the_blend_is_not_counted_twice(self):
		"""It is in the packaging BOM *and* implied by the fill quantity."""
		result = plan(self.site["company"], [{"item_code": self.sku, "qty": PACKS}])

		blend_lines = [row for row in result["lines"] if row["item_code"] == self.blend]
		self.assertEqual(len(blend_lines), 1)
		self.assertAlmostEqual(blend_lines[0]["required_qty"], 50.0, places=4)

	# --- loss allowance -----------------------------------------------------

	def test_a_loss_allowance_raises_every_requirement(self):
		result = plan(self.site["company"], [{"item_code": self.sku, "qty": PACKS}], loss_percent=2)

		self.assertEqual(result["loss_percent"], 2)
		self.assertAlmostEqual(self.line(result, self.blend)["required_qty"], 51.0, places=4)
		self.assertAlmostEqual(self.line(result, self.pouch)["required_qty"], 1020.0, places=2)

	def test_the_company_policy_supplies_the_default_allowance(self):
		frappe.db.set_value(
			"FM Manufacturing Policy", self.site["company"], "packing_loss_percent", 5
		)
		frappe.clear_document_cache("FM Manufacturing Policy", self.site["company"])

		result = plan(self.site["company"], [{"item_code": self.sku, "qty": PACKS}])

		self.assertEqual(result["loss_percent"], 5)
		self.assertAlmostEqual(self.line(result, self.pouch)["required_qty"], 1050.0, places=2)

	def test_a_negative_allowance_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			plan(self.site["company"], [{"item_code": self.sku, "qty": PACKS}], loss_percent=-1)

	# --- the stock position -------------------------------------------------

	def test_stock_on_hand_reduces_the_shortage(self):
		self.receive(self.pouch, 400)

		result = plan(self.site["company"], [{"item_code": self.sku, "qty": PACKS}])
		pouch = self.line(result, self.pouch)

		self.assertAlmostEqual(pouch["actual_qty"], 400.0, places=2)
		self.assertAlmostEqual(pouch["available_qty"], 400.0, places=2)
		self.assertAlmostEqual(pouch["shortage_qty"], 600.0, places=2)

	def test_enough_stock_means_no_shortage(self):
		self.receive(self.pouch, 1200)

		pouch = self.line(
			plan(self.site["company"], [{"item_code": self.sku, "qty": PACKS}]), self.pouch
		)
		self.assertEqual(pouch["shortage_qty"], 0.0)

	def test_the_four_parts_of_the_position_are_reported_separately(self):
		self.receive(self.label, 100)

		label = self.line(
			plan(self.site["company"], [{"item_code": self.sku, "qty": PACKS}]), self.label
		)
		for key in ("actual_qty", "committed_qty", "requested_qty", "expected_qty"):
			self.assertIn(key, label)

	# --- Material Requests --------------------------------------------------

	def test_a_shortage_becomes_a_draft_material_request(self):
		result = create_material_request(
			self.site["company"], [{"item_code": self.sku, "qty": PACKS}], self.site["stores"]
		)

		self.assertTrue(result["created"])
		doc = frappe.get_doc("Material Request", result["material_request"])
		# A proposal, never an order: a buyer decides.
		self.assertEqual(doc.docstatus, 0)
		self.assertEqual(doc.material_request_type, "Purchase")

		rows = {row.item_code: flt(row.qty) for row in doc.items}
		self.assertAlmostEqual(rows[self.pouch], 1000.0, places=2)
		self.assertAlmostEqual(rows[self.blend], 50.0, places=4)

	def test_planning_the_same_run_twice_requests_nothing_the_second_time(self):
		first = create_material_request(
			self.site["company"], [{"item_code": self.sku, "qty": PACKS}], self.site["stores"]
		)

		second = create_material_request(
			self.site["company"], [{"item_code": self.sku, "qty": PACKS}], self.site["stores"]
		)

		self.assertFalse(second["created"])
		self.assertEqual(second["material_request"], first["material_request"])

	def test_an_open_request_is_netted_off_the_next_plan(self):
		"""Arithmetic, not just the key: indented_qty is already counted."""
		created = create_material_request(
			self.site["company"], [{"item_code": self.sku, "qty": PACKS}], self.site["stores"]
		)
		frappe.get_doc("Material Request", created["material_request"]).submit()

		pouch = self.line(
			plan(self.site["company"], [{"item_code": self.sku, "qty": PACKS}]), self.pouch
		)
		self.assertAlmostEqual(pouch["requested_qty"], 1000.0, places=2)
		self.assertEqual(pouch["shortage_qty"], 0.0)

	def test_nothing_is_requested_when_there_is_no_shortage(self):
		self.receive(self.pouch, 2000)
		self.receive(self.label, 2000)
		self.receive(self.blend, 100)

		result = create_material_request(
			self.site["company"], [{"item_code": self.sku, "qty": PACKS}], self.site["stores"]
		)

		self.assertFalse(result["created"])
		self.assertIsNone(result["material_request"])
		self.assertEqual(result["shortages"], [])

	def test_another_companys_warehouse_is_refused(self):
		with self.assertRaises(frappe.PermissionError):
			create_material_request(
				self.site["company"],
				[{"item_code": self.sku, "qty": PACKS}],
				self.site["foreign_warehouse"],
			)

	# --- what the planner must not guess ------------------------------------

	def test_a_missing_conversion_is_reported_not_assumed(self):
		"""A silent factor of 1 would plan 50,000 kg instead of 50."""
		odd = fixtures.ensure_uom(f"{fixtures.PREFIX} Scoop")
		frappe.db.set_value("Item", self.sku, "fm_pack_uom", odd)
		frappe.clear_document_cache("Item", self.sku)

		result = plan(self.site["company"], [{"item_code": self.sku, "qty": PACKS}])

		self.assertFalse([row for row in result["lines"] if row["item_code"] == self.blend])
		self.assertTrue(any("conversion" in note.lower() for note in result["notes"]))

	def test_an_item_without_a_pack_size_is_skipped_with_a_note(self):
		plain = fixtures.ensure_item(
			f"APlanPlain {self.tag}", nature="Finished Good", has_batch=False, uom=NOS
		)

		result = plan(self.site["company"], [{"item_code": plain, "qty": 100}])

		self.assertEqual(result["lines"], [])
		self.assertTrue(any(plain in note for note in result["notes"]))

"""Phase 2: the production workspace's search, availability and stage action."""

import frappe
from frappe.utils import flt

from food_manufacturing.api.production import get_production_queue, get_work_order_detail
from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.tests import fixtures

KG = "Kg"


class TestProductionWorkspace(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		fixtures.ensure_uom(KG)

	def setUp(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		fixtures.cleanup_users()

		self.tag = self._testMethodName.replace("test_", "")[:12]
		self.policy = fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		self.chilli = fixtures.ensure_item(f"APwChilli {self.tag}", nature="Raw Material", has_batch=False)
		self.cumin = fixtures.ensure_item(f"APwCumin {self.tag}", nature="Raw Material", has_batch=False)
		self.blend = fixtures.ensure_item(f"APwBlend {self.tag}", nature="Bulk Blend", has_batch=False)

	def tearDown(self):
		frappe.set_user("Administrator")
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		fixtures.cleanup_users()

	def receive(self, item_code, qty):
		doc = frappe.get_doc({
			"doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
			"purpose": "Material Receipt", "company": self.site["company"],
			"items": [{"item_code": item_code, "qty": qty,
			           "t_warehouse": self.site["stores"], "basic_rate": 100}],
		})
		doc.insert(); doc.submit()
		return doc

	def approve_recipe(self):
		doc = frappe.get_doc({
			"doctype": "FM Recipe", "item": self.blend, "company": self.site["company"],
			"batch_size": 100, "batch_uom": KG,
			"ingredients": [
				{"item_code": self.chilli, "percentage": 60, "uom": KG},
				{"item_code": self.cumin, "percentage": 40, "uom": KG},
			],
		})
		doc.insert(); doc.submit()
		return doc

	def work_order(self, bom, qty=100):
		doc = frappe.get_doc({
			"doctype": "Work Order", "production_item": self.blend, "bom_no": bom,
			"qty": qty, "company": self.site["company"],
			"fg_warehouse": self.site["stores"], "wip_warehouse": self.site["stores"],
			"source_warehouse": self.site["stores"], "use_multi_level_bom": 0, "skip_transfer": 1,
		})
		doc.insert(); doc.submit()
		return doc

	def stocked_run(self):
		self.receive(self.chilli, 200)
		self.receive(self.cumin, 200)
		return self.work_order(self.approve_recipe().bom)

	# --- search and paging, in the query ------------------------------------

	def test_search_matches_the_work_order_number(self):
		order = self.stocked_run()
		found = get_production_queue(self.site["company"], search=order.name)
		self.assertEqual([row["name"] for row in found], [order.name])

	def test_search_matches_what_the_run_makes(self):
		order = self.stocked_run()
		found = get_production_queue(self.site["company"], search="APwBlend")
		self.assertIn(order.name, [row["name"] for row in found])

	def test_search_that_matches_nothing_returns_nothing(self):
		self.stocked_run()
		self.assertEqual(get_production_queue(self.site["company"], search="zzz-no-such"), [])

	def test_paging_happens_in_the_query(self):
		self.receive(self.chilli, 500)
		self.receive(self.cumin, 500)
		bom = self.approve_recipe().bom
		first, second = self.work_order(bom, 10), self.work_order(bom, 10)

		page = get_production_queue(self.site["company"], limit=1)
		self.assertEqual(len(page), 1)

		names = {row["name"] for row in get_production_queue(self.site["company"], limit=1, start=1)}
		self.assertTrue(names)
		self.assertNotEqual(names, {page[0]["name"]})
		self.assertLessEqual(names | {page[0]["name"]}, {first.name, second.name})

	# --- material availability ----------------------------------------------

	def test_a_stocked_run_reads_as_ready(self):
		order = self.stocked_run()
		row = next(r for r in get_production_queue(self.site["company"]) if r["name"] == order.name)

		self.assertTrue(row["material_ready"])
		self.assertEqual(row["short_items"], 0)

	def test_a_run_missing_an_ingredient_is_not_ready(self):
		self.receive(self.chilli, 200)
		order = self.work_order(self.approve_recipe().bom)

		row = next(r for r in get_production_queue(self.site["company"]) if r["name"] == order.name)
		self.assertFalse(row["material_ready"])
		self.assertEqual(row["short_items"], 1)

	def test_the_detail_says_how_short_each_ingredient_is(self):
		self.receive(self.chilli, 200)
		self.receive(self.cumin, 10)
		order = self.work_order(self.approve_recipe().bom)

		detail = get_work_order_detail(order.name)
		rows = {row["item_code"]: row for row in detail["ingredients"]}

		self.assertAlmostEqual(rows[self.cumin]["outstanding_qty"], 40.0, places=2)
		self.assertAlmostEqual(rows[self.cumin]["available_qty"], 10.0, places=2)
		self.assertAlmostEqual(rows[self.cumin]["short_qty"], 30.0, places=2)
		self.assertEqual(flt(rows[self.chilli]["short_qty"]), 0.0)

	# --- the one action for this stage --------------------------------------

	def test_a_ready_run_offers_completion(self):
		order = self.stocked_run()
		action = get_work_order_detail(order.name)["next_action"]

		self.assertEqual(action["action"], "complete")
		self.assertTrue(action["enabled"])
		self.assertIsNone(action["reason"])

	def test_a_short_run_offers_completion_but_disabled_with_a_reason(self):
		"""Hiding the action would leave an operator hunting for it."""
		self.receive(self.chilli, 200)
		order = self.work_order(self.approve_recipe().bom)

		action = get_work_order_detail(order.name)["next_action"]
		self.assertEqual(action["action"], "complete")
		self.assertFalse(action["enabled"])
		self.assertIn("Short of", action["reason"])

	def test_the_detail_reports_overall_readiness(self):
		self.receive(self.chilli, 200)
		order = self.work_order(self.approve_recipe().bom)
		self.assertFalse(get_work_order_detail(order.name)["material_ready"])

"""Acceptance examples for the owner dashboard's exception lists.

The point of these: a figure on a live screen must come from a record. The
previous "Ready to start" counted every open run, because the queue it filtered
carries no availability at all.
"""

import frappe
from frappe.utils import add_days, today

from food_manufacturing.api.exceptions import get_exceptions
from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.tests import fixtures

KG = "Kg"


class TestExceptions(FMTestCase):
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
		self.chilli = fixtures.ensure_item(f"AExChilli {self.tag}", nature="Raw Material", has_batch=False)
		self.cumin = fixtures.ensure_item(f"AExCumin {self.tag}", nature="Raw Material", has_batch=False)
		self.blend = fixtures.ensure_item(f"AExBlend {self.tag}", nature="Bulk Blend", has_batch=False)

	def tearDown(self):
		frappe.set_user("Administrator")
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		fixtures.cleanup_users()

	def receive(self, item_code, qty, rate=100):
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

	def approve_recipe(self):
		doc = frappe.get_doc({
			"doctype": "FM Recipe",
			"item": self.blend,
			"company": self.site["company"],
			"batch_size": 100,
			"batch_uom": KG,
			"ingredients": [
				{"item_code": self.chilli, "percentage": 60, "uom": KG},
				{"item_code": self.cumin, "percentage": 40, "uom": KG},
			],
		})
		doc.insert()
		doc.submit()
		return doc

	def work_order(self, bom, qty=100, planned_end=None):
		doc = frappe.get_doc({
			"doctype": "Work Order",
			"production_item": self.blend,
			"bom_no": bom,
			"qty": qty,
			"company": self.site["company"],
			"fg_warehouse": self.site["stores"],
			"wip_warehouse": self.site["stores"],
			"source_warehouse": self.site["stores"],
			"use_multi_level_bom": 0,
			"skip_transfer": 1,
		})
		if planned_end:
			# ERPNext refuses an end date before the start, and the start
			# defaults to now - so a run planned to finish last week has to say
			# it started before that.
			doc.planned_start_date = add_days(planned_end, -1)
			doc.planned_end_date = planned_end
		doc.insert()
		doc.submit()
		return doc

	# --- material shortages -------------------------------------------------

	def test_a_run_with_stock_for_everything_is_not_short(self):
		self.receive(self.chilli, 200)
		self.receive(self.cumin, 200)
		recipe = self.approve_recipe()
		self.work_order(recipe.bom)

		self.assertEqual(get_exceptions(self.site["company"])["material_short"], [])

	def test_a_run_missing_an_ingredient_is_short(self):
		self.receive(self.chilli, 200)
		# No cumin received at all.
		recipe = self.approve_recipe()
		order = self.work_order(recipe.bom)

		short = get_exceptions(self.site["company"])["material_short"]
		rows = {row["work_order"]: row for row in short}

		self.assertIn(order.name, rows)
		items = {item["item_code"]: item for item in rows[order.name]["items"]}
		self.assertIn(self.cumin, items)
		self.assertNotIn(self.chilli, items)

	def test_the_shortage_is_the_gap_not_the_requirement(self):
		self.receive(self.chilli, 200)
		self.receive(self.cumin, 10)
		recipe = self.approve_recipe()
		order = self.work_order(recipe.bom)

		row = next(r for r in get_exceptions(self.site["company"])["material_short"]
		           if r["work_order"] == order.name)
		cumin = next(i for i in row["items"] if i["item_code"] == self.cumin)

		# 40 kg needed, 10 kg on hand.
		self.assertAlmostEqual(cumin["required_qty"], 40.0, places=2)
		self.assertAlmostEqual(cumin["available_qty"], 10.0, places=2)
		self.assertAlmostEqual(cumin["short_qty"], 30.0, places=2)

	def test_stock_in_another_companys_warehouse_does_not_count(self):
		"""A shortage judged against someone else's stock is not a shortage."""
		self.receive(self.chilli, 200)
		recipe = self.approve_recipe()
		order = self.work_order(recipe.bom)

		short = {row["work_order"] for row in get_exceptions(self.site["company"])["material_short"]}
		self.assertIn(order.name, short)

	# --- delayed runs -------------------------------------------------------

	def test_a_run_past_its_end_date_is_delayed(self):
		self.receive(self.chilli, 200)
		self.receive(self.cumin, 200)
		recipe = self.approve_recipe()
		order = self.work_order(recipe.bom, planned_end=add_days(today(), -3))

		delayed = {row["work_order"]: row for row in get_exceptions(self.site["company"])["delayed_runs"]}
		self.assertIn(order.name, delayed)
		self.assertEqual(delayed[order.name]["days_late"], 3)

	def test_a_run_still_within_its_date_is_not_delayed(self):
		self.receive(self.chilli, 200)
		self.receive(self.cumin, 200)
		recipe = self.approve_recipe()
		order = self.work_order(recipe.bom, planned_end=add_days(today(), 5))

		delayed = {row["work_order"] for row in get_exceptions(self.site["company"])["delayed_runs"]}
		self.assertNotIn(order.name, delayed)

	# --- permissions --------------------------------------------------------

	def test_a_user_who_cannot_read_work_orders_sees_no_runs(self):
		"""Never an error, and never someone else's rows: just nothing."""
		self.receive(self.chilli, 200)
		recipe = self.approve_recipe()
		self.work_order(recipe.bom, planned_end=add_days(today(), -1))

		# Sales User can read Company - so the endpoint opens - but not Work
		# Order, which is the condition under test. Stock User would read both.
		user = fixtures.ensure_user("excnobody", ("FM Quality Inspector", "Sales User"))
		frappe.set_user(user)

		result = get_exceptions(self.site["company"])
		self.assertEqual(result["material_short"], [])
		self.assertEqual(result["delayed_runs"], [])

	def test_a_company_the_user_cannot_read_is_refused(self):
		user = fixtures.ensure_user("excnone", ())
		frappe.set_user(user)

		with self.assertRaises(frappe.PermissionError):
			get_exceptions(self.site["company"])

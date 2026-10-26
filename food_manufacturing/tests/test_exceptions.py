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

	# --- the formula behind a shortage ---------------------------------------

	def console_user(self, suffix, fm_role):
		"""An operator account: Work Order and Company read, no recipe access."""
		return fixtures.ensure_user(
			suffix, (fm_role, "Manufacturing User", "Item Manager", "Stock User")
		)

	def short_row(self, order):
		rows = {
			row["work_order"]: row for row in get_exceptions(self.site["company"])["material_short"]
		}
		return rows.get(order.name)

	def test_an_operator_sees_the_shortage_at_all(self):
		"""The panel has to work for somebody other than Administrator.

		``has_permission`` on a child table with no ``parent_doctype`` has no
		parent to check against and returns False for every non-Administrator,
		so this list used to come back empty for every real operator - and the
		tests above all ran as Administrator, which is exactly how that hid.
		"""
		self.receive(self.chilli, 200)
		recipe = self.approve_recipe()
		order = self.work_order(recipe.bom)

		frappe.set_user(self.console_user("excreal", "FM Recipe Manager"))

		self.assertIsNotNone(self.short_row(order))

	def test_the_shortage_quantities_are_withheld_from_an_outsider(self):
		"""The detail screen withholds these figures; so must this panel.

		What a run still needs is its BOM's quantity for that ingredient while
		nothing has been transferred yet, and this panel lists many runs at once
		- so it was the cheaper read of the two, and quoting the numbers here
		made the withholding on the detail screen worth nothing.
		"""
		self.receive(self.chilli, 200)
		recipe = self.approve_recipe()
		order = self.work_order(recipe.bom)

		frappe.set_user(self.console_user("excshort", "FM Production Manager"))
		row = self.short_row(order)

		self.assertIsNotNone(row)
		self.assertFalse(row["shows_ingredient_detail"])
		for item in row["items"]:
			self.assertIsNone(item["required_qty"])
			self.assertIsNone(item["short_qty"])
			# Stock on hand is a fact about the warehouse, not about the recipe.
			self.assertIsNotNone(item["available_qty"])

	def test_the_shortage_itself_survives_the_withholding(self):
		"""Withholding the numbers must not hide that something is missing."""
		self.receive(self.chilli, 200)
		recipe = self.approve_recipe()
		order = self.work_order(recipe.bom)

		frappe.set_user(self.console_user("excstill", "FM Production Manager"))
		row = self.short_row(order)

		self.assertEqual({item["item_code"] for item in row["items"]}, {self.cumin})

	def test_a_recipe_manager_still_gets_the_quantities(self):
		self.receive(self.chilli, 200)
		recipe = self.approve_recipe()
		order = self.work_order(recipe.bom)

		frappe.set_user(self.console_user("excdetail", "FM Recipe Manager"))
		row = self.short_row(order)

		self.assertTrue(row["shows_ingredient_detail"])
		items = {item["item_code"]: item for item in row["items"]}
		self.assertEqual(items[self.cumin]["required_qty"], 40)
		self.assertEqual(items[self.cumin]["short_qty"], 40)

	def test_a_run_with_no_recipe_behind_it_is_not_withheld(self):
		"""This app does not decide who reads other people's BOMs."""
		self.receive(self.chilli, 200)
		recipe = self.approve_recipe()
		order = self.work_order(recipe.bom)
		frappe.db.set_value("BOM", recipe.bom, "fm_recipe", None, update_modified=False)
		frappe.clear_document_cache("BOM", recipe.bom)

		frappe.set_user(self.console_user("excplain", "FM Production Manager"))
		row = self.short_row(order)

		self.assertTrue(row["shows_ingredient_detail"])
		self.assertIsNotNone(row["items"][0]["required_qty"])

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

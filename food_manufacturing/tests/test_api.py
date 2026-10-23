"""API layer: the four operator screens' endpoints.

Two things are asserted throughout: that each endpoint returns what the screen
needs, and that it cannot be used to get round a server rule. The second matters
more - a whitelisted method is a public door.
"""

import frappe
from frappe.utils import add_days, flt, today

from food_manufacturing.api import dispatch as dispatch_api
from food_manufacturing.api import production as production_api
from food_manufacturing.api import quality as quality_api
from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.tests import fixtures

KG = "Kg"


class APITestCase(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		fixtures.ensure_uom(KG)

	def setUp(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		fixtures.cleanup_users()

		self.original_batch_setting = frappe.db.get_single_value(
			"Stock Settings", "enable_serial_and_batch_no_for_item"
		)
		frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

		self.policy = fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		self.tag = self._testMethodName.replace("test_", "")
		self.chilli = fixtures.ensure_item(f"AChilli {self.tag}", nature="Raw Material")
		self.cumin = fixtures.ensure_item(f"ACumin {self.tag}", nature="Raw Material")
		self.blend = fixtures.ensure_item(f"ABlend {self.tag}", nature="Bulk Blend")

	def tearDown(self):
		frappe.set_user("Administrator")
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		fixtures.cleanup_users()
		frappe.db.set_single_value(
			"Stock Settings",
			"enable_serial_and_batch_no_for_item",
			self.original_batch_setting,
		)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

	def receive(self, item_code, qty, batch_id, status="Released", rate=100):
		batch = fixtures.ensure_batch(item_code, batch_id, status=status)
		doc = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"purpose": "Material Receipt",
				"company": self.site["company"],
				"items": [
					{
						"item_code": item_code,
						"qty": qty,
						"t_warehouse": self.site["stores"],
						"basic_rate": rate,
						"batch_no": batch,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		doc.insert()
		doc.submit()
		return batch

	def approve_recipe(self):
		doc = frappe.get_doc(
			{
				"doctype": "FM Recipe",
				"item": self.blend,
				"company": self.site["company"],
				"batch_size": 100,
				"batch_uom": KG,
				"ingredients": [
					{"item_code": self.chilli, "percentage": 60, "uom": KG},
					{"item_code": self.cumin, "percentage": 40, "uom": KG},
				],
			}
		)
		doc.insert()
		doc.submit()
		return doc

	def make_work_order(self, bom, qty=100):
		doc = frappe.get_doc(
			{
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
			}
		)
		doc.insert()
		doc.submit()
		return doc


class TestProductionAPI(APITestCase):
	def test_queue_lists_the_open_work_order(self):
		self.receive(self.chilli, 60, f"C-{self.tag}")
		self.receive(self.cumin, 40, f"U-{self.tag}")
		recipe = self.approve_recipe()
		work_order = self.make_work_order(recipe.bom)

		queue = production_api.get_production_queue(self.site["company"])
		names = {row["name"]: row for row in queue}
		self.assertIn(work_order.name, names)
		self.assertEqual(flt(names[work_order.name]["pending_qty"]), 100)

	def test_queue_reports_the_items_unit_not_the_work_order_default(self):
		"""A blend planned in kilograms must not read as "500 Nos".

		``Work Order.stock_uom`` is only fetched by the Desk form, so an order
		created through the API or an import keeps the ``Nos`` default. The
		Item is the authority.
		"""
		self.receive(self.chilli, 60, f"C-{self.tag}")
		self.receive(self.cumin, 40, f"U-{self.tag}")
		recipe = self.approve_recipe()
		work_order = self.make_work_order(recipe.bom)

		item_uom = frappe.db.get_value("Item", self.blend, "stock_uom")
		self.assertEqual(frappe.db.get_value("Work Order", work_order.name, "stock_uom"), "Nos")

		queue = {row["name"]: row for row in production_api.get_production_queue(self.site["company"])}
		self.assertEqual(queue[work_order.name]["stock_uom"], item_uom)

	def test_detail_reports_the_items_unit(self):
		self.receive(self.chilli, 60, f"C-{self.tag}")
		self.receive(self.cumin, 40, f"U-{self.tag}")
		recipe = self.approve_recipe()
		work_order = self.make_work_order(recipe.bom)

		detail = production_api.get_work_order_detail(work_order.name)
		self.assertEqual(
			detail["work_order"]["stock_uom"],
			frappe.db.get_value("Item", self.blend, "stock_uom"),
		)

	def test_detail_offers_released_lots_in_fefo_order(self):
		chilli = self.receive(self.chilli, 60, f"C-{self.tag}")
		self.receive(self.cumin, 40, f"U-{self.tag}")
		recipe = self.approve_recipe()
		work_order = self.make_work_order(recipe.bom)

		detail = production_api.get_work_order_detail(work_order.name)
		by_item = {row["item_code"]: row for row in detail["ingredients"]}
		self.assertEqual(flt(by_item[self.chilli]["required_qty"]), 60)
		lots = [lot["batch_no"] for lot in by_item[self.chilli]["available_lots"]]
		self.assertIn(chilli, lots)

	def test_detail_hides_unreleased_lots(self):
		"""The console must not offer a lot the server would then refuse."""
		self.receive(self.chilli, 60, f"C-{self.tag}", status="Quarantine")
		self.receive(self.cumin, 40, f"U-{self.tag}")
		recipe = self.approve_recipe()
		work_order = self.make_work_order(recipe.bom)

		detail = production_api.get_work_order_detail(work_order.name)
		by_item = {row["item_code"]: row for row in detail["ingredients"]}
		self.assertEqual(by_item[self.chilli]["available_lots"], [])

	def test_finish_run_posts_the_entry_and_returns_yield(self):
		self.receive(self.chilli, 60, f"C-{self.tag}")
		self.receive(self.cumin, 40, f"U-{self.tag}")
		recipe = self.approve_recipe()
		work_order = self.make_work_order(recipe.bom)

		fg_batch = fixtures.ensure_batch(self.blend, f"B-{self.tag}", status=None)
		result = production_api.finish_production_run(
			work_order.name, qty=97, finished_batch=fg_batch, process_loss_qty=3
		)

		self.assertTrue(result["stock_entry"])
		self.assertEqual(flt(result["produced_qty"]), 97)
		self.assertEqual(flt(result["process_loss_qty"]), 3)
		self.assertEqual(flt(result["yield_percent"]), 97)
		self.assertEqual(result["yield_basis"], KG)

	def test_finish_run_rejects_more_than_the_work_order(self):
		self.receive(self.chilli, 60, f"C-{self.tag}")
		self.receive(self.cumin, 40, f"U-{self.tag}")
		recipe = self.approve_recipe()
		work_order = self.make_work_order(recipe.bom)

		with self.assertRaises(frappe.ValidationError):
			production_api.finish_production_run(work_order.name, qty=500)

	def test_finish_run_rejects_non_positive_qty(self):
		recipe = self.approve_recipe()
		work_order = self.make_work_order(recipe.bom)
		with self.assertRaises(frappe.ValidationError):
			production_api.finish_production_run(work_order.name, qty=0)

	def test_finish_run_still_enforces_the_quality_gate(self):
		"""The API cannot be used to consume an unreleased lot."""
		self.receive(self.chilli, 60, f"C-{self.tag}", status="Quarantine")
		self.receive(self.cumin, 40, f"U-{self.tag}")
		recipe = self.approve_recipe()
		work_order = self.make_work_order(recipe.bom)

		with self.assertRaises(frappe.ValidationError):
			production_api.finish_production_run(work_order.name, qty=100)

	def test_operator_without_write_cannot_finish_a_run(self):
		recipe = self.approve_recipe()
		work_order = self.make_work_order(recipe.bom)

		user = fixtures.ensure_user("qcinspector", ("FM Quality Inspector",))
		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			production_api.finish_production_run(work_order.name, qty=10)


class TestQualityAPI(APITestCase):
	def test_queue_lists_quarantined_stock(self):
		batch = self.receive(self.chilli, 60, f"C-{self.tag}", status="Quarantine")
		queue = {row["name"]: row for row in quality_api.get_release_queue(self.site["company"])}
		self.assertIn(batch, queue)
		self.assertEqual(flt(queue[batch]["qty"]), 60)

	def test_queue_excludes_released_stock(self):
		batch = self.receive(self.chilli, 60, f"C-{self.tag}", status="Released")
		queue = {row["name"] for row in quality_api.get_release_queue(self.site["company"])}
		self.assertNotIn(batch, queue)

	def test_queue_excludes_batches_with_no_stock(self):
		batch = fixtures.ensure_batch(self.chilli, f"EMPTY-{self.tag}", status="Quarantine")
		queue = {row["name"] for row in quality_api.get_release_queue(self.site["company"])}
		self.assertNotIn(batch, queue)

	def test_counts_match_the_queue(self):
		self.receive(self.chilli, 60, f"C-{self.tag}", status="Quarantine")
		self.receive(self.cumin, 40, f"U-{self.tag}", status="Hold")
		counts = quality_api.get_queue_counts(self.site["company"])
		self.assertEqual(counts["quarantine"], 1)
		self.assertEqual(counts["hold"], 1)
		self.assertEqual(counts["total"], 2)

	def test_batch_context_includes_history_and_genealogy(self):
		batch = self.receive(self.chilli, 60, f"C-{self.tag}", status="Quarantine")
		context = quality_api.get_batch_context(batch)
		self.assertEqual(context["batch"]["name"], batch)
		self.assertEqual(context["batch"]["quality_status"], "Quarantine")
		self.assertIn("genealogy", context)
		self.assertEqual(context["history"], [])

	def test_record_decision_releases_the_batch(self):
		batch = self.receive(self.chilli, 60, f"C-{self.tag}", status="Quarantine")
		result = quality_api.record_decision(batch, self.site["company"], "Release")
		self.assertEqual(result["quality_status"], "Released")
		self.assertEqual(result["previous_status"], "Quarantine")

	def test_record_decision_requires_a_reason_to_reject(self):
		batch = self.receive(self.chilli, 60, f"C-{self.tag}", status="Quarantine")
		with self.assertRaises(frappe.ValidationError):
			quality_api.record_decision(batch, self.site["company"], "Reject")

	def test_record_decision_rejects_an_unknown_decision(self):
		batch = self.receive(self.chilli, 60, f"C-{self.tag}", status="Quarantine")
		with self.assertRaises(frappe.ValidationError):
			quality_api.record_decision(batch, self.site["company"], "Approve")

	def test_inspector_cannot_record_a_decision_through_the_api(self):
		"""The whole point of the permission check on a public door."""
		batch = self.receive(self.chilli, 60, f"C-{self.tag}", status="Quarantine")
		user = fixtures.ensure_user("inspector", ("FM Quality Inspector",))

		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			quality_api.record_decision(batch, self.site["company"], "Release")

	def test_quality_manager_can_record_a_decision_through_the_api(self):
		batch = self.receive(self.chilli, 60, f"C-{self.tag}", status="Quarantine")
		user = fixtures.ensure_user("qm", ("FM Quality Manager",))

		frappe.set_user(user)
		result = quality_api.record_decision(batch, self.site["company"], "Release")
		self.assertEqual(result["quality_status"], "Released")


class TestDispatchAPI(APITestCase):
	def setUp(self):
		super().setUp()
		self.sku = fixtures.ensure_item(f"ASKU {self.tag}", nature="Finished Good")

	def test_picklist_suggests_the_earliest_expiring_batch(self):
		sooner = self.receive(self.sku, 10, f"SOON-{self.tag}")
		later = self.receive(self.sku, 10, f"LATE-{self.tag}")
		frappe.db.set_value("Batch", sooner, "expiry_date", add_days(today(), 20))
		frappe.db.set_value("Batch", later, "expiry_date", add_days(today(), 300))
		frappe.clear_document_cache("Batch", sooner)
		frappe.clear_document_cache("Batch", later)

		candidates = dispatch_api.get_fefo_batches(self.sku, self.site["stores"], self.site["company"])
		picks, shortfall = dispatch_api._allocate(candidates, 15)
		self.assertEqual(picks[0]["batch_no"], sooner)
		self.assertEqual(flt(picks[0]["qty"]), 10)
		self.assertEqual(picks[1]["batch_no"], later)
		self.assertEqual(flt(shortfall), 0)

	def test_allocation_reports_a_shortfall(self):
		self.receive(self.sku, 3, f"ONLY-{self.tag}")
		candidates = dispatch_api.get_fefo_batches(self.sku, self.site["stores"], self.site["company"])
		_picks, shortfall = dispatch_api._allocate(candidates, 10)
		self.assertEqual(flt(shortfall), 7)

	def test_candidates_are_annotated_with_shelf_life_and_blocking(self):
		batch = self.receive(self.sku, 10, f"NEAR-{self.tag}")
		frappe.db.set_value(
			"Batch",
			batch,
			{"expiry_date": add_days(today(), 36), "manufacturing_date": add_days(today(), -324)},
		)
		frappe.clear_document_cache("Batch", batch)

		policy = fixtures.ensure_policy(self.site, min_remaining_shelf_life_percent=25)
		candidates = dispatch_api.get_fefo_batches(self.sku, self.site["stores"], self.site["company"])
		annotated = {row["batch_no"]: row for row in dispatch_api._annotate(candidates, policy)}

		self.assertLess(annotated[batch]["remaining_shelf_life_percent"], 25)
		self.assertIsNotNone(annotated[batch]["blocked_reason"])

	def test_open_sales_orders_requires_read_permission(self):
		user = fixtures.ensure_user("nobody", ())
		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			dispatch_api.get_open_sales_orders(self.site["company"])

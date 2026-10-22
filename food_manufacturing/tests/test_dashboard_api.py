"""Dashboard aggregates.

The honesty cases matter most here: a dashboard that quietly reports a plausible
wrong number is worse than one that reports nothing.
"""

import frappe
from frappe.utils import add_days, flt, today

from food_manufacturing.api.dashboard import get_dashboard
from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.tests import fixtures

KG = "Kg"


class TestDashboardAPI(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		fixtures.ensure_uom(KG)

	def setUp(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		self.original_batch_setting = frappe.db.get_single_value(
			"Stock Settings", "enable_serial_and_batch_no_for_item"
		)
		frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

		self.policy = fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		self.tag = self._testMethodName.replace("test_", "")
		self.chilli = fixtures.ensure_item(f"DChilli {self.tag}", nature="Raw Material")
		self.cumin = fixtures.ensure_item(f"DCumin {self.tag}", nature="Raw Material")
		self.blend = fixtures.ensure_item(f"DBlend {self.tag}", nature="Bulk Blend")

	def tearDown(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		frappe.db.set_single_value(
			"Stock Settings",
			"enable_serial_and_batch_no_for_item",
			self.original_batch_setting,
		)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

	def receive(self, item_code, qty, batch_id, status="Released"):
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
						"basic_rate": 100,
						"batch_no": batch,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		doc.insert()
		doc.submit()
		return batch

	def run_blend(self, process_loss_qty=3):
		from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

		self.receive(self.chilli, 60, f"C-{self.tag}")
		self.receive(self.cumin, 40, f"U-{self.tag}")

		recipe = frappe.get_doc(
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
		recipe.insert()
		recipe.submit()

		work_order = frappe.get_doc(
			{
				"doctype": "Work Order",
				"production_item": self.blend,
				"bom_no": recipe.bom,
				"qty": 100,
				"company": self.site["company"],
				"fg_warehouse": self.site["stores"],
				"wip_warehouse": self.site["stores"],
				"source_warehouse": self.site["stores"],
				"use_multi_level_bom": 0,
				"skip_transfer": 1,
			}
		)
		work_order.insert()
		work_order.submit()

		entry = frappe.get_doc(make_stock_entry(work_order.name, "Manufacture", 100))
		bulk = fixtures.ensure_batch(self.blend, f"B-{self.tag}", status=None)
		for row in entry.items:
			row.use_serial_batch_fields = 1
			if row.item_code == self.blend and row.t_warehouse:
				row.batch_no = bulk
				if process_loss_qty:
					row.qty = 100 - process_loss_qty
					row.transfer_qty = 100 - process_loss_qty
		if process_loss_qty:
			entry.process_loss_qty = process_loss_qty
		entry.insert()
		entry.submit()

		work_order.reload()
		return work_order, bulk

	# -- shape ----------------------------------------------------------------

	def test_returns_every_panel(self):
		data = get_dashboard(self.site["company"])
		for key in (
			"kpis",
			"yield_trend",
			"production_by_item",
			"quality_mix",
			"expiry_buckets",
		):
			self.assertIn(key, data)

	def test_empty_company_returns_no_fabricated_numbers(self):
		"""Nothing produced means no average yield - not zero percent."""
		data = get_dashboard(self.site["company"])
		self.assertIsNone(data["kpis"]["average_yield_percent"])
		self.assertEqual(data["kpis"]["completed_runs"], 0)
		self.assertEqual(data["yield_trend"], [])

	# -- KPIs -----------------------------------------------------------------

	def test_average_yield_reflects_the_run(self):
		self.run_blend(process_loss_qty=3)
		kpis = get_dashboard(self.site["company"])["kpis"]
		self.assertEqual(flt(kpis["average_yield_percent"]), 97)
		self.assertEqual(kpis["completed_runs"], 1)

	def test_flagged_run_is_counted(self):
		fixtures.ensure_policy(
			self.site, require_incoming_inspection=0, yield_variance_tolerance_percent=1
		)
		self.run_blend(process_loss_qty=3)
		kpis = get_dashboard(self.site["company"])["kpis"]
		self.assertEqual(kpis["yield_flagged"], 1)

	def test_pending_qc_counts_quarantined_stock(self):
		self.receive(self.chilli, 10, f"Q-{self.tag}", status="Quarantine")
		kpis = get_dashboard(self.site["company"])["kpis"]
		self.assertEqual(kpis["pending_qc"], 1)

	# -- series ---------------------------------------------------------------

	def test_yield_trend_carries_actual_and_planned(self):
		work_order, _bulk = self.run_blend(process_loss_qty=3)
		trend = get_dashboard(self.site["company"])["yield_trend"]
		labels = {row["label"]: row for row in trend}
		self.assertIn(work_order.name, labels)
		self.assertEqual(flt(labels[work_order.name]["actual"]), 97)
		self.assertEqual(flt(labels[work_order.name]["planned"]), 100)

	def test_production_by_item_keeps_the_uom_with_the_row(self):
		self.run_blend(process_loss_qty=3)
		rows = get_dashboard(self.site["company"])["production_by_item"]
		by_item = {row["item_code"]: row for row in rows}
		self.assertIn(self.blend, by_item)
		self.assertEqual(flt(by_item[self.blend]["value"]), 97)
		self.assertEqual(by_item[self.blend]["uom"], KG)
		self.assertEqual(flt(by_item[self.blend]["loss"]), 3)

	def test_quality_mix_orders_statuses_to_keep_close_colours_apart(self):
		"""Released, Quarantine, Rejected, Hold - never warning beside serious."""
		self.receive(self.chilli, 10, f"R-{self.tag}", status="Released")
		self.receive(self.cumin, 10, f"Q-{self.tag}", status="Quarantine")

		mix = get_dashboard(self.site["company"])["quality_mix"]
		labels = [row["label"] for row in mix]
		self.assertEqual(labels, ["Released", "Quarantine"])
		roles = {row["label"]: row["role"] for row in mix}
		self.assertEqual(roles["Released"], "good")
		self.assertEqual(roles["Quarantine"], "warning")

	def test_quality_mix_ignores_batches_with_no_stock(self):
		fixtures.ensure_batch(self.chilli, f"EMPTY-{self.tag}", status="Quarantine")
		mix = get_dashboard(self.site["company"])["quality_mix"]
		self.assertEqual(mix, [])

	def test_expiry_buckets_lead_with_the_most_urgent(self):
		near = self.receive(self.chilli, 10, f"NEAR-{self.tag}")
		far = self.receive(self.cumin, 10, f"FAR-{self.tag}")
		frappe.db.set_value("Batch", near, "expiry_date", add_days(today(), 3))
		frappe.db.set_value("Batch", far, "expiry_date", add_days(today(), 60))
		frappe.clear_document_cache("Batch", near)
		frappe.clear_document_cache("Batch", far)

		buckets = get_dashboard(self.site["company"])["expiry_buckets"]
		labels = [row["label"] for row in buckets]
		# Most urgent first: the row needing action leads the chart.
		self.assertEqual(labels, ["Within 7 days", "31-90 days"])

	def test_requires_read_permission(self):
		fixtures.cleanup_users()
		user = fixtures.ensure_user("nobody", ())
		frappe.set_user(user)
		try:
			with self.assertRaises(frappe.PermissionError):
				get_dashboard(self.site["company"])
		finally:
			frappe.set_user("Administrator")
			fixtures.cleanup_users()

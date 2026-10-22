"""Near-expiry detection, driven by the per-company alert horizon."""

import frappe
from frappe.utils import add_days, flt, today

from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.tasks.near_expiry import get_near_expiry_batches
from food_manufacturing.tests import fixtures


class TestNearExpiry(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		fixtures.ensure_uom("Kg")

	def setUp(self):
		fixtures.cleanup()
		self.original_batch_setting = frappe.db.get_single_value(
			"Stock Settings", "enable_serial_and_batch_no_for_item"
		)
		frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

		self.policy = fixtures.ensure_policy(self.site, near_expiry_alert_days=30)
		tag = self._testMethodName.replace("test_", "")[:16]
		self.tag = tag
		self.item = fixtures.ensure_item(f"Exp {tag}", nature="Finished Good")

	def tearDown(self):
		fixtures.cleanup()
		frappe.db.set_single_value(
			"Stock Settings",
			"enable_serial_and_batch_no_for_item",
			self.original_batch_setting,
		)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

	def stock_batch(self, batch_id, qty, expiry, status="Released"):
		batch = fixtures.ensure_batch(self.item, batch_id, status=status)

		if qty:
			doc = frappe.get_doc(
				{
					"doctype": "Stock Entry",
					"stock_entry_type": "Material Receipt",
					"purpose": "Material Receipt",
					"company": self.site["company"],
					"items": [
						{
							"item_code": self.item,
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

		frappe.db.set_value("Batch", batch, "expiry_date", expiry)
		frappe.clear_document_cache("Batch", batch)
		return batch

	def names(self, within_days=30):
		return {
			row["batch_no"]
			for row in get_near_expiry_batches(self.site["company"], within_days)
		}

	def test_batch_inside_the_horizon_is_reported(self):
		batch = self.stock_batch(f"SOON-{self.tag}", 5, add_days(today(), 10))
		self.assertIn(batch, self.names())

	def test_batch_outside_the_horizon_is_not_reported(self):
		batch = self.stock_batch(f"FAR-{self.tag}", 5, add_days(today(), 200))
		self.assertNotIn(batch, self.names())

	def test_already_expired_batch_is_reported(self):
		"""The most urgent case must not be filtered out."""
		batch = self.stock_batch(f"GONE-{self.tag}", 5, add_days(today(), -5))
		self.assertIn(batch, self.names())

	def test_horizon_is_configurable(self):
		batch = self.stock_batch(f"MID-{self.tag}", 5, add_days(today(), 60))
		self.assertNotIn(batch, self.names(30))
		self.assertIn(batch, self.names(90))

	def test_batch_with_no_stock_is_not_reported(self):
		"""An expiring batch with nothing left in it is nobody's problem."""
		batch = self.stock_batch(f"EMPTY-{self.tag}", 0, add_days(today(), 10))
		self.assertNotIn(batch, self.names())

	def test_rejected_batches_are_excluded(self):
		"""Already rejected, so not an expiry action for anyone."""
		batch = self.stock_batch(
			f"REJ-{self.tag}", 5, add_days(today(), 10), status="Rejected"
		)
		self.assertNotIn(batch, self.names())

	def test_days_to_expiry_and_qty_are_reported(self):
		batch = self.stock_batch(f"SOON-{self.tag}", 7, add_days(today(), 10))
		row = next(
			r
			for r in get_near_expiry_batches(self.site["company"], 30)
			if r["batch_no"] == batch
		)
		self.assertEqual(row["days_to_expiry"], 10)
		self.assertEqual(flt(row["qty"]), 7)
		self.assertEqual(row["item_code"], self.item)

	def test_other_companies_stock_is_not_reported(self):
		batch = self.stock_batch(f"SOON-{self.tag}", 5, add_days(today(), 10))
		other = {
			row["batch_no"]
			for row in get_near_expiry_batches(self.site["foreign_company"], 30)
		}
		self.assertNotIn(batch, other)

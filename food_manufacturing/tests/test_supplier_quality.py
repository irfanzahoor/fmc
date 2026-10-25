"""Cost per usable unit, and the quality split behind it.

The headline figure is the one worth protecting with tests: a supplier whose
material is cheap per kilogram received and expensive per kilogram *usable*.
Getting the quantity wrong would quietly move that number, so the regression
that inflated received quantities by counting warehouse transfers is covered
here too.
"""

import frappe
from frappe.utils import add_days, flt, today

from food_manufacturing.compat.stock import get_lot_feature, set_lot_feature
from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.quality.supplier_quality import (
	get_fm_qc_rejected_qty,
	get_fm_received_qty,
	get_fm_usable_qty,
	get_supplier_lot_quality,
)
from food_manufacturing.tests import fixtures

SUPPLIER = f"{fixtures.PREFIX} Lot Quality Supplier"


class TestSupplierQuality(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		cls.kg = fixtures.ensure_uom("Kg")
		cls.supplier = cls.ensure_supplier()

	@classmethod
	def ensure_supplier(cls):
		if not frappe.db.exists("Supplier", SUPPLIER):
			frappe.get_doc(
				{
					"doctype": "Supplier",
					"supplier_name": SUPPLIER,
					"supplier_group": frappe.db.get_value(
						"Supplier Group", {"is_group": 0}, "name", order_by="name asc"
					),
				}
			).insert()

		return SUPPLIER

	def setUp(self):
		fixtures.cleanup()
		self.original_batch_setting = get_lot_feature()
		set_lot_feature(1)
		self.policy = fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		self.tag = self._testMethodName.replace("test_", "")[:24]
		self.chilli = fixtures.ensure_item(f"Chilli {self.tag}", nature="Raw Material")

	def tearDown(self):
		fixtures.cleanup()
		set_lot_feature(self.original_batch_setting)

	# -- helpers --------------------------------------------------------------

	def receive(self, qty, rate, batch_id, status=None, warehouse=None):
		batch = fixtures.ensure_batch(self.chilli, batch_id, status=status)
		frappe.db.set_value("Batch", batch, "supplier", self.supplier)
		frappe.clear_document_cache("Batch", batch)

		doc = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"purpose": "Material Receipt",
				"company": self.site["company"],
				"items": [
					{
						"item_code": self.chilli,
						"qty": qty,
						"t_warehouse": warehouse or self.site["stores"],
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

	def transfer(self, batch, qty, source, target):
		doc = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Transfer",
				"purpose": "Material Transfer",
				"company": self.site["company"],
				"items": [
					{
						"item_code": self.chilli,
						"qty": qty,
						"s_warehouse": source,
						"t_warehouse": target,
						"batch_no": batch,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		doc.insert()
		doc.submit()
		return doc

	def row_for(self, **kwargs):
		rows = get_supplier_lot_quality(
			company=self.site["company"], supplier=self.supplier, item_code=self.chilli, **kwargs
		)
		return rows[0] if rows else None

	# -- the headline figure --------------------------------------------------

	def test_a_clean_lot_costs_the_same_received_and_usable(self):
		self.receive(100, 300, f"LOT-SQ1-{self.tag}", status="Released")

		row = self.row_for()

		self.assertEqual(flt(row["received_qty"]), 100)
		self.assertEqual(flt(row["usable_qty"]), 100)
		self.assertEqual(flt(row["cost_per_received_unit"]), 300)
		self.assertEqual(flt(row["cost_per_usable_unit"]), 300)
		self.assertEqual(flt(row["cost_penalty_percent"]), 0)

	def test_rejection_raises_the_cost_of_what_survives(self):
		"""The whole point: 300/kg bought, 20% rejected, 375/kg usable."""
		self.receive(80, 300, f"LOT-SQ2A-{self.tag}", status="Released")
		self.receive(20, 300, f"LOT-SQ2B-{self.tag}", status="Rejected")

		row = self.row_for()

		self.assertEqual(flt(row["received_qty"]), 100)
		self.assertEqual(flt(row["rejected_qty"]), 20)
		self.assertEqual(flt(row["reject_percent"]), 20)
		self.assertEqual(flt(row["usable_qty"]), 80)
		self.assertEqual(flt(row["cost_per_received_unit"]), 300)
		self.assertEqual(flt(row["cost_per_usable_unit"]), 375)
		self.assertEqual(flt(row["cost_penalty_percent"]), 25)

	def test_a_cheaper_supplier_can_be_the_expensive_one(self):
		"""The comparison a buyer actually needs, asserted end to end."""
		self.receive(90, 280, f"LOT-SQ3A-{self.tag}", status="Released")
		self.receive(10, 280, f"LOT-SQ3B-{self.tag}", status="Rejected")

		row = self.row_for()

		# Bought cheaper than the 300/kg lot above, but a usable kilogram costs
		# more than that lot's 300 once the rejection is carried.
		self.assertEqual(flt(row["cost_per_received_unit"]), 280)
		self.assertGreater(flt(row["cost_per_usable_unit"]), 300)

	def test_a_fully_rejected_lot_states_no_usable_rate(self):
		"""Inventing a rate here would understate the loss, so it stays zero."""
		self.receive(40, 260, f"LOT-SQ4-{self.tag}", status="Rejected")

		row = self.row_for()

		self.assertEqual(flt(row["usable_qty"]), 0)
		self.assertEqual(flt(row["reject_percent"]), 100)
		self.assertEqual(flt(row["cost_per_usable_unit"]), 0)
		self.assertEqual(flt(row["cost_penalty_percent"]), 0)

	# -- what counts as usable ------------------------------------------------

	def test_a_held_lot_still_counts_as_usable(self):
		"""Holding is not a decision against the supplier, so it is not charged."""
		self.receive(70, 300, f"LOT-SQ5A-{self.tag}", status="Released")
		self.receive(30, 300, f"LOT-SQ5B-{self.tag}", status="Hold")

		row = self.row_for()

		self.assertEqual(flt(row["held_qty"]), 30)
		self.assertEqual(flt(row["rejected_qty"]), 0)
		self.assertEqual(flt(row["usable_qty"]), 100)

	def test_a_lot_awaiting_qc_is_reported_separately(self):
		self.receive(50, 300, f"LOT-SQ6-{self.tag}", status="Quarantine")

		row = self.row_for()

		self.assertEqual(flt(row["quarantine_qty"]), 50)
		self.assertEqual(flt(row["released_qty"]), 0)
		self.assertEqual(flt(row["usable_qty"]), 50)

	# -- quantities -----------------------------------------------------------

	def test_an_internal_transfer_does_not_inflate_the_received_qty(self):
		"""Regression: both legs of a transfer are in the ledger.

		Counting the inward leg doubled the quantity *and* the value, which left
		the rate correct and every total wrong - the reason it went unnoticed.
		"""
		batch = self.receive(
			120, 300, f"LOT-SQ7-{self.tag}", status="Released", warehouse=self.site["quarantine"]
		)
		self.transfer(batch, 120, self.site["quarantine"], self.site["stores"])

		row = self.row_for()

		self.assertEqual(flt(row["received_qty"]), 120)
		self.assertEqual(flt(row["received_value"]), 36000)
		self.assertEqual(flt(row["cost_per_usable_unit"]), 300)

	def test_a_manufactured_batch_is_not_a_supplier_lot(self):
		"""The report is about bought material; a blend has no supplier."""
		self.receive(10, 300, f"LOT-SQ8-{self.tag}", status="Released")
		blend = fixtures.ensure_item(f"Blend {self.tag}", nature="Bulk Blend")
		made = fixtures.ensure_batch(blend, f"BULK-SQ8-{self.tag}", status="Released")

		rows = get_supplier_lot_quality(company=self.site["company"])

		self.assertNotIn(made, [row.get("item_code") for row in rows])
		self.assertNotIn(blend, [row["item_code"] for row in rows])

	# -- filters --------------------------------------------------------------

	def test_the_date_window_excludes_earlier_receipts(self):
		self.receive(60, 300, f"LOT-SQ9-{self.tag}", status="Released")

		self.assertIsNone(self.row_for(from_date=add_days(today(), 1)))
		self.assertIsNotNone(self.row_for(from_date=today(), to_date=today()))

	def test_another_company_does_not_see_the_lot(self):
		self.receive(60, 300, f"LOT-SQ10-{self.tag}", status="Released")

		rows = get_supplier_lot_quality(
			company=self.site["foreign_company"], supplier=self.supplier, item_code=self.chilli
		)

		self.assertEqual(rows, [])

	def test_rows_are_worst_first(self):
		"""The supplier to look at should not need sorting by hand."""
		other = fixtures.ensure_item(f"Cumin {self.tag}", nature="Raw Material")
		clean = fixtures.ensure_batch(other, f"LOT-SQ11-{self.tag}", status="Released")
		frappe.db.set_value("Batch", clean, "supplier", self.supplier)
		frappe.clear_document_cache("Batch", clean)
		frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"purpose": "Material Receipt",
				"company": self.site["company"],
				"items": [
					{
						"item_code": other,
						"qty": 100,
						"t_warehouse": self.site["stores"],
						"basic_rate": 100,
						"batch_no": clean,
						"use_serial_batch_fields": 1,
					}
				],
			}
		).insert().submit()

		self.receive(50, 300, f"LOT-SQ11B-{self.tag}", status="Released")
		self.receive(50, 300, f"LOT-SQ11C-{self.tag}", status="Rejected")

		rows = get_supplier_lot_quality(company=self.site["company"], supplier=self.supplier)
		rates = [flt(row["cost_per_usable_unit"]) for row in rows]

		self.assertEqual(rates, sorted(rates, reverse=True))

	# -- scorecard variables --------------------------------------------------

	def test_the_scorecard_variables_report_the_period(self):
		"""ERPNext calls these with a period, so they take one object, not kwargs."""
		self.receive(70, 300, f"LOT-SQ12A-{self.tag}", status="Released")
		self.receive(30, 300, f"LOT-SQ12B-{self.tag}", status="Rejected")

		period = frappe._dict(
			supplier=self.supplier, start_date=add_days(today(), -1), end_date=today()
		)

		self.assertEqual(flt(get_fm_received_qty(period)), 100)
		self.assertEqual(flt(get_fm_qc_rejected_qty(period)), 30)
		self.assertEqual(flt(get_fm_usable_qty(period)), 70)

	def test_a_scorecard_variable_is_zero_outside_the_period(self):
		self.receive(70, 300, f"LOT-SQ13-{self.tag}", status="Released")

		period = frappe._dict(
			supplier=self.supplier, start_date=add_days(today(), -30), end_date=add_days(today(), -2)
		)

		self.assertEqual(flt(get_fm_received_qty(period)), 0)

	def test_the_registered_variable_paths_resolve(self):
		"""ERPNext resolves a variable path with a getattr chain, not an import.

		If this breaks, a scorecard period fails at the moment somebody tries to
		compute it, which is exactly when nobody is watching the logs.
		"""
		from erpnext.buying.doctype.supplier_scorecard_period.supplier_scorecard_period import (
			import_string_path,
		)

		from food_manufacturing.setup.scorecard import FM_VARIABLES

		for variable in FM_VARIABLES:
			self.assertTrue(callable(import_string_path(variable["path"])), msg=variable["path"])

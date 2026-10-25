"""Receiving: quarantine routing and supplier lot capture on Purchase Receipt.

This submits a real Purchase Receipt so the standard ERPNext batch-creation path
runs. The framework rolls the transaction back after each test, so no stock
ledger entry survives.

Precondition: where ERPNext gates lot handling behind a site-wide switch it
refuses to create a Serial and Batch Bundle while that switch is off, and
batched receiving is impossible without it. These tests turn it on through
``compat.stock`` and restore the original value in tearDown - belt and braces on
top of the transaction rollback, because Stock Settings is a Single and
therefore site-wide. On a version with no such switch both calls are no-ops.
"""

import frappe
from frappe.utils import add_days, getdate, today

from food_manufacturing.compat.stock import get_lot_feature, set_lot_feature
from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.overrides.purchase_receipt import stamp_batches
from food_manufacturing.quality.batch_eligibility import get_row_batches
from food_manufacturing.tests import fixtures


class TestReceiving(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		cls.supplier = frappe.db.get_value("Supplier", {}, "name")

	def setUp(self):
		if not self.supplier:
			self.skipTest("Site has no Supplier")

		self.original_batch_setting = get_lot_feature()
		set_lot_feature(1)

		fixtures.cleanup()
		self.policy = fixtures.ensure_policy(self.site)
		self.raw = fixtures.ensure_item("Coriander", nature="Raw Material")
		self.unclassified = fixtures.ensure_item("Misc", nature=None)

	def tearDown(self):
		fixtures.cleanup()
		set_lot_feature(self.original_batch_setting)

	def make_receipt(self, item_code, warehouse, lot_no=None, submit=True, mfg_date=None):
		"""Build a receipt. Batch numbering is left entirely to ERPNext."""
		doc = frappe.get_doc(
			{
				"doctype": "Purchase Receipt",
				"company": self.site["company"],
				"supplier": self.supplier,
				"items": [
					{
						"item_code": item_code,
						"qty": 10,
						"rate": 100,
						"warehouse": warehouse,
						"fm_supplier_lot_no": lot_no,
						"fm_supplier_mfg_date": mfg_date,
					}
				],
			}
		)
		doc.insert()
		if submit:
			doc.submit()

		return doc

	def batches_of(self, doc):
		"""Batch numbers the receipt actually created, via row or bundle.

		Read back from the database for the same reason the override does: the
		bundle link is written with frappe.db.set_value during submit.
		"""
		rows = frappe.get_all(
			"Purchase Receipt Item",
			filters={"parent": doc.name},
			fields=["name", "item_code", "batch_no", "serial_and_batch_bundle"],
			order_by="idx asc",
		)
		by_row = get_row_batches(rows)
		return sorted({b for batches in by_row.values() for b in batches})

	# -- 2.3 quarantine routing ----------------------------------------------

	def test_inspected_material_is_routed_to_quarantine(self):
		doc = self.make_receipt(self.raw, self.site["stores"], submit=False)
		self.assertEqual(doc.items[0].warehouse, self.site["quarantine"])

	def test_unclassified_item_is_left_alone(self):
		"""Enabling this app must not change existing purchasing."""
		doc = self.make_receipt(self.unclassified, self.site["stores"], submit=False)
		self.assertEqual(doc.items[0].warehouse, self.site["stores"])

	def test_no_routing_when_inspection_not_required(self):
		fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		doc = self.make_receipt(self.raw, self.site["stores"], submit=False)
		self.assertEqual(doc.items[0].warehouse, self.site["stores"])

	def test_no_routing_without_a_policy(self):
		frappe.db.delete("FM Manufacturing Policy", {"company": self.site["company"]})
		doc = self.make_receipt(self.raw, self.site["stores"], submit=False)
		self.assertEqual(doc.items[0].warehouse, self.site["stores"])

	# -- 2.2 supplier lot capture and quarantine status ----------------------

	def test_received_batch_is_quarantined_with_supplier_lot(self):
		doc = self.make_receipt(self.raw, self.site["stores"], lot_no="SUP-LOT-77")

		batches = self.batches_of(doc)
		self.assertTrue(batches, msg="ERPNext should have created a batch for this item")

		for batch_no in batches:
			values = frappe.db.get_value(
				"Batch", batch_no, ["fm_quality_status", "fm_supplier_lot_no"], as_dict=True
			)
			self.assertEqual(values.fm_quality_status, "Quarantine", msg=batch_no)
			self.assertEqual(values.fm_supplier_lot_no, "SUP-LOT-77", msg=batch_no)

	def test_received_batch_lands_in_quarantine_warehouse(self):
		doc = self.make_receipt(self.raw, self.site["stores"], lot_no="SUP-LOT-80")
		self.assertEqual(doc.items[0].warehouse, self.site["quarantine"])

		sle_warehouses = frappe.get_all(
			"Stock Ledger Entry",
			filters={"voucher_type": "Purchase Receipt", "voucher_no": doc.name},
			pluck="warehouse",
			order_by="name asc",
		)
		self.assertEqual(set(sle_warehouses), {self.site["quarantine"]})

	def test_received_batch_cannot_then_be_consumed(self):
		"""End to end: receive, then try to use it without a release."""
		doc = self.make_receipt(self.raw, self.site["stores"], lot_no="SUP-LOT-78")
		batches = self.batches_of(doc)
		self.assertTrue(batches)

		issue = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Issue",
				"purpose": "Material Issue",
				"company": self.site["company"],
				"items": [
					{
						"item_code": self.raw,
						"qty": 1,
						"s_warehouse": self.site["quarantine"],
						"batch_no": batches[0],
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			issue.run_method("validate")

	def test_release_then_consume_succeeds(self):
		"""The happy path: a released batch becomes consumable."""
		fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		doc = self.make_receipt(self.raw, self.site["stores"], lot_no="SUP-LOT-81")
		batch_no = self.batches_of(doc)[0]

		release = frappe.get_doc(
			{
				"doctype": "FM Batch Release",
				"batch": batch_no,
				"company": self.site["company"],
				"decision": "Release",
			}
		)
		release.insert()
		release.submit()

		issue = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Issue",
				"purpose": "Material Issue",
				"company": self.site["company"],
				"items": [
					{
						"item_code": self.raw,
						"qty": 1,
						"s_warehouse": self.site["quarantine"],
						"batch_no": batch_no,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		issue.run_method("validate")  # must not raise

	def test_existing_status_is_not_overwritten(self):
		"""Receiving more of an already-released batch must not re-quarantine it."""
		doc = self.make_receipt(self.raw, self.site["stores"], lot_no="SUP-LOT-79")
		batch_no = self.batches_of(doc)[0]

		frappe.db.set_value("Batch", batch_no, "fm_quality_status", "Released")
		frappe.clear_document_cache("Batch", batch_no)

		# Re-running the receipt's own stamping step must be a no-op.
		stamp_batches(doc)
		self.assertEqual(frappe.db.get_value("Batch", batch_no, "fm_quality_status"), "Released")

	# -- 2.2 the supplier's manufacturing date is the one that counts ---------

	def perishable(self, shelf_life_days=180):
		"""An item ERPNext will date a batch for: expiring, with a shelf life."""
		frappe.db.set_value(
			"Item",
			self.raw,
			{"has_expiry_date": 1, "shelf_life_in_days": shelf_life_days},
		)
		frappe.clear_document_cache("Item", self.raw)

	def dates_of(self, batch_no) -> dict:
		return frappe.db.get_value(
			"Batch", batch_no, ["manufacturing_date", "expiry_date"], as_dict=True
		)

	def test_the_supplier_manufacturing_date_reaches_the_batch(self):
		"""ERPNext dates a batch from the receipt, which is not when it was made.

		A lot the supplier blended 100 days ago arrives today, and left alone
		the batch claims it was made today - so it reads as 100 days fresher
		than it is, and the remaining-shelf-life check, the near-expiry alert
		and FEFO all inherit that error.
		"""
		self.perishable(shelf_life_days=180)
		made = getdate(add_days(today(), -100))

		doc = self.make_receipt(self.raw, self.site["stores"], lot_no="SUP-MFG-1", mfg_date=made)
		batch_no = self.batches_of(doc)[0]

		dates = self.dates_of(batch_no)
		self.assertEqual(getdate(dates.manufacturing_date), made)
		# Shelf life runs from when it was made, not from when it arrived.
		self.assertEqual(getdate(dates.expiry_date), getdate(add_days(made, 180)))

	def test_a_supplier_date_never_makes_a_batch_look_fresher(self):
		"""A mistyped date must not be able to extend a batch's life.

		Both dates only ever move earlier. A supplier date in the future - a
		typo, or a year written wrong - would otherwise push the expiry out and
		make stock dispatchable that should not be.
		"""
		self.perishable(shelf_life_days=180)

		doc = self.make_receipt(
			self.raw,
			self.site["stores"],
			lot_no="SUP-MFG-2",
			mfg_date=getdate(add_days(today(), 10)),
		)
		batch_no = self.batches_of(doc)[0]

		dates = self.dates_of(batch_no)
		self.assertEqual(getdate(dates.manufacturing_date), getdate(today()))
		self.assertEqual(getdate(dates.expiry_date), getdate(add_days(today(), 180)))

	def test_a_receipt_without_a_supplier_date_is_left_to_erpnext(self):
		self.perishable(shelf_life_days=180)

		doc = self.make_receipt(self.raw, self.site["stores"], lot_no="SUP-MFG-3")
		batch_no = self.batches_of(doc)[0]

		dates = self.dates_of(batch_no)
		self.assertEqual(getdate(dates.manufacturing_date), getdate(today()))
		self.assertEqual(getdate(dates.expiry_date), getdate(add_days(today(), 180)))

	def test_the_supplier_date_is_recorded_even_when_inspection_is_off(self):
		"""A date somebody entered is a fact about the material, not a policy."""
		fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		self.perishable(shelf_life_days=90)
		made = getdate(add_days(today(), -30))

		doc = self.make_receipt(self.raw, self.site["stores"], mfg_date=made)
		batch_no = self.batches_of(doc)[0]

		self.assertEqual(getdate(self.dates_of(batch_no).manufacturing_date), made)

"""Receiving: quarantine routing and supplier lot capture on Purchase Receipt.

This submits a real Purchase Receipt so the standard ERPNext batch-creation path
runs. The framework rolls the transaction back after each test, so no stock
ledger entry survives.

Precondition: ERPNext refuses to create a Serial and Batch Bundle unless
``Stock Settings.enable_serial_and_batch_no_for_item`` is on, and batched
receiving is impossible without it. The host site has it off, so these tests
turn it on and restore the original value in tearDown - belt and braces on top
of the transaction rollback, because Stock Settings is a Single and therefore
site-wide.
"""

import frappe

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

		self.original_batch_setting = frappe.db.get_single_value(
			"Stock Settings", "enable_serial_and_batch_no_for_item"
		)
		frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

		fixtures.cleanup()
		self.policy = fixtures.ensure_policy(self.site)
		self.raw = fixtures.ensure_item("Coriander", nature="Raw Material")
		self.unclassified = fixtures.ensure_item("Misc", nature=None)

	def tearDown(self):
		fixtures.cleanup()
		frappe.db.set_single_value(
			"Stock Settings",
			"enable_serial_and_batch_no_for_item",
			self.original_batch_setting,
		)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

	def make_receipt(self, item_code, warehouse, lot_no=None, submit=True):
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

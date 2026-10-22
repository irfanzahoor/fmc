"""Compatibility layer must resolve to the names this site actually has."""

import frappe

from food_manufacturing.compat import erpnext_major, frappe_major, meta_has_field
from food_manufacturing.compat.bom import (
	byproduct_child_doctype,
	byproduct_field,
	supports_work_order_byproducts,
)
from food_manufacturing.compat.testing import FMTestCase


class TestCompat(FMTestCase):
	def test_majors_are_matched(self):
		"""The app supports matched majors only."""
		self.assertEqual(
			frappe_major(),
			erpnext_major(),
			msg="Frappe and ERPNext majors must match for this app",
		)
		self.assertIn(frappe_major(), (15, 16))

	def test_bom_byproduct_field_resolves_to_a_real_field(self):
		fieldname = byproduct_field("BOM")
		self.assertIsNotNone(fieldname, msg="BOM must expose a by-product table on v15 and v16")
		self.assertTrue(meta_has_field("BOM", fieldname))

		if frappe_major() >= 16:
			self.assertEqual(fieldname, "secondary_items")
		else:
			self.assertEqual(fieldname, "scrap_items")

	def test_bom_byproduct_child_doctype_exists(self):
		child = byproduct_child_doctype("BOM")
		self.assertIsNotNone(child)
		self.assertTrue(frappe.db.exists("DocType", child))

	def test_work_order_byproducts_only_on_v16(self):
		"""Work Order grew its own by-product table in v16."""
		self.assertEqual(supports_work_order_byproducts(), frappe_major() >= 16)

	def test_process_loss_is_version_neutral(self):
		"""Non-recoverable loss needs no shim: same fields on both majors."""
		self.assertTrue(meta_has_field("BOM", "process_loss_percentage"))
		self.assertTrue(meta_has_field("BOM", "process_loss_qty"))
		self.assertTrue(meta_has_field("Work Order", "process_loss_qty"))

	def test_batch_genealogy_fields_are_version_neutral(self):
		"""Split-batch tracing relies on these existing on both majors."""
		for fieldname in ("parent_batch", "expiry_date", "manufacturing_date", "supplier"):
			self.assertTrue(meta_has_field("Batch", fieldname), msg=fieldname)

	def test_serial_and_batch_bundle_present(self):
		self.assertTrue(frappe.db.exists("DocType", "Serial and Batch Bundle"))

"""End-to-end blending run against real ERPNext stock.

This is the acceptance scenario's blending step, run for real: receive two
ingredient lots into quarantine, release them, produce a bulk blend against an
approved recipe, then assert the derived yield and the lot genealogy.

The site's ``Stock Settings.enable_serial_and_batch_no_for_item`` is turned on
for the duration and restored in tearDown, because batched stock is impossible
without it and the host site has it off.

Each test gets its **own** items and batches, keyed off the test name. The
framework rolls back per class rather than per test, so tests that post real
stock would otherwise see each other's ledger entries - which first showed up as
a required quantity of 120 kg against 60 kg of stock.
"""

import frappe
from frappe.utils import flt

from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.production.genealogy import get_consumed_lots, get_work_order_batches
from food_manufacturing.tests import fixtures


class TestProductionFlow(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		cls.kg = fixtures.ensure_uom("Kg")

	def setUp(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()

		self.original_batch_setting = frappe.db.get_single_value(
			"Stock Settings", "enable_serial_and_batch_no_for_item"
		)
		frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

		self.policy = fixtures.ensure_policy(
			self.site, require_incoming_inspection=0, yield_variance_tolerance_percent=2
		)

		# Unique per test: stock posted by one test must not be visible to the next.
		self.tag = self._testMethodName.replace("test_", "")[:24]
		self.blend = fixtures.ensure_item(f"Blend {self.tag}", nature="Bulk Blend")
		self.chilli = fixtures.ensure_item(f"Chilli {self.tag}", nature="Raw Material")
		self.cumin = fixtures.ensure_item(f"Cumin {self.tag}", nature="Raw Material")

	def tearDown(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		frappe.db.set_single_value(
			"Stock Settings",
			"enable_serial_and_batch_no_for_item",
			self.original_batch_setting,
		)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

	# -- helpers --------------------------------------------------------------

	def receive(self, item_code, qty, batch_id):
		"""Material Receipt straight into the quarantine warehouse."""
		batch = fixtures.ensure_batch(item_code, batch_id, status=None)
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

	def release(self, batch):
		doc = frappe.get_doc(
			{
				"doctype": "FM Batch Release",
				"batch": batch,
				"company": self.site["company"],
				"decision": "Release",
			}
		)
		doc.insert()
		doc.submit()
		return doc

	def approve_recipe(self):
		doc = frappe.get_doc(
			{
				"doctype": "FM Recipe",
				"item": self.blend,
				"company": self.site["company"],
				"batch_size": 100,
				"batch_uom": self.kg,
				"ingredients": [
					{"item_code": self.chilli, "percentage": 60, "uom": self.kg},
					{"item_code": self.cumin, "percentage": 40, "uom": self.kg},
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

	def manufacture(self, work_order, fg_qty, batch_id, process_loss_qty=0):
		"""Submit a Manufacture Stock Entry against the Work Order."""
		from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

		entry = frappe.get_doc(make_stock_entry(work_order.name, "Manufacture", fg_qty))

		# Name the finished-goods batch so the genealogy assertions can find it.
		fg_batch = fixtures.ensure_batch(self.blend, batch_id, status=None)
		for row in entry.items:
			row.use_serial_batch_fields = 1
			if row.item_code == self.blend and row.t_warehouse:
				row.batch_no = fg_batch

		if process_loss_qty:
			entry.process_loss_qty = process_loss_qty

		entry.insert()
		entry.submit()
		return entry

	# -- the run --------------------------------------------------------------

	def test_blend_run_records_yield_and_genealogy(self):
		chilli_lot = self.receive(self.chilli, 60, f"LOT-CHILLI-{self.tag}")
		cumin_lot = self.receive(self.cumin, 40, f"LOT-CUMIN-{self.tag}")
		self.release(chilli_lot)
		self.release(cumin_lot)

		recipe = self.approve_recipe()
		work_order = self.make_work_order(recipe.bom, qty=100)
		self.manufacture(work_order, 100, f"BULK-{self.tag}")

		work_order.reload()
		self.assertEqual(flt(work_order.produced_qty), 100)

		# Yield figures were written by the Stock Entry hook.
		self.assertEqual(work_order.fm_yield_basis, "Kg")
		self.assertEqual(flt(work_order.fm_planned_input_qty), 100)
		self.assertEqual(flt(work_order.fm_actual_input_qty), 100)
		self.assertEqual(flt(work_order.fm_actual_yield_percent), 100)
		self.assertEqual(work_order.fm_yield_flagged, 0)

		# Genealogy is derived from the ledger, not stored.
		batches = get_work_order_batches(work_order.name)
		consumed = {(e["item_code"], e["batch_no"]): flt(e["qty"]) for e in batches["consumed"]}
		produced = {(e["item_code"], e["batch_no"]): flt(e["qty"]) for e in batches["produced"]}

		self.assertEqual(consumed.get((self.chilli, chilli_lot)), 60)
		self.assertEqual(consumed.get((self.cumin, cumin_lot)), 40)
		self.assertEqual(produced.get((self.blend, f"_FMT-BULK-{self.tag}")), 100)

	def test_consumed_lots_carry_supplier_lot_metadata(self):
		chilli_lot = self.receive(self.chilli, 60, f"LOT-CHILLI-{self.tag}")
		cumin_lot = self.receive(self.cumin, 40, f"LOT-CUMIN-{self.tag}")
		frappe.db.set_value("Batch", chilli_lot, "fm_supplier_lot_no", "SUP-A")
		self.release(chilli_lot)
		self.release(cumin_lot)

		recipe = self.approve_recipe()
		work_order = self.make_work_order(recipe.bom, qty=100)
		self.manufacture(work_order, 100, f"BULK-{self.tag}")

		lots = {entry["batch_no"]: entry for entry in get_consumed_lots(work_order.name)}
		self.assertEqual(lots[chilli_lot]["supplier_lot_no"], "SUP-A")
		self.assertEqual(lots[chilli_lot]["quality_status"], "Released")

	def test_unreleased_ingredient_blocks_the_run(self):
		"""The quality gate holds inside the production path too."""
		self.receive(self.chilli, 60, f"LOT-CHILLI-{self.tag}")
		self.receive(self.cumin, 40, f"LOT-CUMIN-{self.tag}")
		# Put one lot in quarantine instead of releasing it.
		frappe.db.set_value(
			"Batch", f"_FMT-LOT-CHILLI-{self.tag}", "fm_quality_status", "Quarantine"
		)
		self.release(f"_FMT-LOT-CUMIN-{self.tag}")

		recipe = self.approve_recipe()
		work_order = self.make_work_order(recipe.bom, qty=100)

		with self.assertRaises(frappe.ValidationError):
			self.manufacture(work_order, 100, f"BULK-{self.tag}")

	def test_cancelling_the_manufacture_entry_resets_the_yield(self):
		chilli_lot = self.receive(self.chilli, 60, f"LOT-CHILLI-{self.tag}")
		cumin_lot = self.receive(self.cumin, 40, f"LOT-CUMIN-{self.tag}")
		self.release(chilli_lot)
		self.release(cumin_lot)

		recipe = self.approve_recipe()
		work_order = self.make_work_order(recipe.bom, qty=100)
		entry = self.manufacture(work_order, 100, f"BULK-{self.tag}")

		work_order.reload()
		self.assertEqual(flt(work_order.fm_actual_yield_percent), 100)

		entry.cancel()
		work_order.reload()
		self.assertEqual(flt(work_order.produced_qty), 0)
		# Nothing produced and nothing consumed, so no actual yield remains.
		self.assertEqual(flt(work_order.fm_actual_yield_percent), 0)

		# And the genealogy no longer claims those batches.
		batches = get_work_order_batches(work_order.name)
		self.assertEqual(batches["consumed"], [])
		self.assertEqual(batches["produced"], [])

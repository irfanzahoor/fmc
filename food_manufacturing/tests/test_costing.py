"""Cost per batch and per pack, and reconciliation with the stock ledger.

The point of these tests is the separation the brief asks for: the actual figure
must be the ledger's own valuation (so it reconciles with ERPNext by
construction) and the planned figure must stay a separate BOM estimate.
"""

import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import flt

from food_manufacturing.compat.bundle import restrict_to_live
from food_manufacturing.compat.stock import get_lot_feature, set_lot_feature
from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.costing.batch_cost import get_batch_actual_cost, get_batch_planned_cost
from food_manufacturing.tests import fixtures

KG = "Kg"


class TestBatchCosting(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		fixtures.ensure_uom(KG)

	def setUp(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		self.original_batch_setting = get_lot_feature()
		set_lot_feature(1)

		self.policy = fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		# The full method name, untruncated: two names that truncate to the same
		# tag would share a batch, and because Frappe rolls back per class
		# rather than per test, their stock would accumulate.
		tag = self._testMethodName.replace("test_", "")
		self.tag = tag
		self.chilli = fixtures.ensure_item(f"CChilli {tag}", nature="Raw Material")
		self.cumin = fixtures.ensure_item(f"CCumin {tag}", nature="Raw Material")
		self.blend = fixtures.ensure_item(f"CBlend {tag}", nature="Bulk Blend")

	def tearDown(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		set_lot_feature(self.original_batch_setting)

	def receive(self, item_code, qty, rate, batch_id):
		batch = fixtures.ensure_batch(item_code, batch_id, status="Released")
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

	def ledger_value(self, batch_no):
		"""Sum stock_value_difference straight from ERPNext's ledger.

		Deliberately a separate query from the costing module's, so the
		reconciliation test is a real comparison rather than a tautology.
		"""
		sle = frappe.qb.DocType("Stock Ledger Entry")
		entry = frappe.qb.DocType("Serial and Batch Entry")

		direct = (
			frappe.qb.from_(sle)
			.select(Sum(sle.stock_value_difference).as_("value"))
			.where(sle.batch_no == batch_no)
			.where(sle.is_cancelled == 0)
			.where(sle.actual_qty > 0)
			.where((sle.serial_and_batch_bundle.isnull()) | (sle.serial_and_batch_bundle == ""))
		).run(as_dict=True)

		bundled = restrict_to_live(
			frappe.qb.from_(sle)
			.inner_join(entry)
			.on(entry.parent == sle.serial_and_batch_bundle)
			.select(Sum(entry.stock_value_difference).as_("value"))
			.where(entry.batch_no == batch_no)
			.where(sle.is_cancelled == 0)
			.where(entry.is_outward == 0),
			entry,
		).run(as_dict=True)

		return flt(direct[0].value if direct else 0) + flt(bundled[0].value if bundled else 0)

	# -- 7.1 cost per batch ---------------------------------------------------

	def test_purchased_batch_rate_matches_what_was_paid(self):
		batch = self.receive(self.chilli, 60, 200, f"C-{self.tag}")
		costs = get_batch_actual_cost([batch])

		self.assertEqual(flt(costs[batch]["qty"]), 60)
		self.assertEqual(flt(costs[batch]["value"]), 12000)
		self.assertEqual(flt(costs[batch]["rate"]), 200)

	def test_purchased_batch_has_no_planned_cost(self):
		"""No BOM estimate exists for bought material, so none is invented."""
		batch = self.receive(self.chilli, 60, 200, f"C-{self.tag}")
		self.assertEqual(get_batch_planned_cost([batch]), {})

	# -- 7.3 reconciliation ---------------------------------------------------

	def test_actual_cost_reconciles_with_the_stock_ledger(self):
		batch = self.receive(self.chilli, 60, 137.5, f"C-{self.tag}")
		costs = get_batch_actual_cost([batch])
		self.assertEqual(flt(costs[batch]["value"], 4), flt(self.ledger_value(batch), 4))

	# -- 7.2 / 7.4 production: value is conserved, loss lifts the unit cost ---

	def produce_blend(self, process_loss_qty=0):
		from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

		chilli = self.receive(self.chilli, 60, 100, f"C-{self.tag}")
		cumin = self.receive(self.cumin, 40, 100, f"U-{self.tag}")

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
		bulk_batch = fixtures.ensure_batch(self.blend, f"B-{self.tag}", status=None)
		for row in entry.items:
			row.use_serial_batch_fields = 1
			if row.item_code == self.blend and row.t_warehouse:
				row.batch_no = bulk_batch
				if process_loss_qty:
					row.qty = 100 - process_loss_qty
					row.transfer_qty = 100 - process_loss_qty

		if process_loss_qty:
			entry.process_loss_qty = process_loss_qty

		entry.insert()
		entry.submit()
		return chilli, cumin, bulk_batch, recipe, work_order

	def test_blend_value_equals_the_value_of_its_inputs(self):
		"""Value is conserved through blending: 100 kg at 100 = 10,000."""
		chilli, cumin, bulk, _recipe, _wo = self.produce_blend()

		inputs = get_batch_actual_cost([chilli, cumin])
		input_value = sum(flt(row["value"]) for row in inputs.values())
		self.assertEqual(flt(input_value), 10000)

		blend_cost = get_batch_actual_cost([bulk])[bulk]
		self.assertEqual(flt(blend_cost["qty"]), 100)
		self.assertEqual(flt(blend_cost["value"], 2), 10000.0)
		self.assertEqual(flt(blend_cost["rate"], 2), 100.0)

	def test_process_loss_raises_the_unit_cost_of_what_survives(self):
		"""3 kg lost from 100 kg worth 10,000 leaves 97 kg at ~103.09.

		This is the documented treatment of wastage: the same value is spread
		over fewer units, so nothing is written off and the surviving stock
		carries the cost. No adjustment of our own is needed.
		"""
		_c, _u, bulk, _recipe, _wo = self.produce_blend(process_loss_qty=3)

		blend_cost = get_batch_actual_cost([bulk])[bulk]
		self.assertEqual(flt(blend_cost["qty"]), 97)
		self.assertEqual(flt(blend_cost["value"], 2), 10000.0)
		self.assertEqual(flt(blend_cost["rate"], 2), flt(10000 / 97, 2))

	def test_planned_cost_is_reported_separately_for_a_made_batch(self):
		_c, _u, bulk, recipe, work_order = self.produce_blend()

		planned = get_batch_planned_cost([bulk])
		self.assertIn(bulk, planned)
		self.assertEqual(planned[bulk]["work_order"], work_order.name)
		self.assertEqual(planned[bulk]["bom"], recipe.bom)

		bom_total, bom_qty = frappe.db.get_value("BOM", recipe.bom, ["total_cost", "quantity"])
		self.assertEqual(
			flt(planned[bulk]["planned_rate"], 4), flt(flt(bom_total) / flt(bom_qty), 4)
		)

	# -- the reports actually return these rows ------------------------------

	def test_batch_cost_report_returns_the_blend(self):
		from frappe.desk.query_report import run

		_c, _u, bulk, _recipe, _wo = self.produce_blend(process_loss_qty=3)

		result = run("FM Batch Cost", filters={"batch_no": bulk}, ignore_prepared_report=True)
		rows = {row["batch_no"]: row for row in result["result"]}
		self.assertIn(bulk, rows)
		self.assertEqual(flt(rows[bulk]["actual_rate"], 2), flt(10000 / 97, 2))
		self.assertIsNotNone(rows[bulk]["planned_rate"])

	def test_production_yield_report_returns_the_run(self):
		from frappe.desk.query_report import run

		_c, _u, _bulk, _recipe, work_order = self.produce_blend(process_loss_qty=3)

		result = run(
			"FM Production Yield",
			filters={"company": self.site["company"]},
			ignore_prepared_report=True,
		)
		rows = {row["name"]: row for row in result["result"]}
		self.assertIn(work_order.name, rows)
		self.assertEqual(flt(rows[work_order.name]["produced_qty"]), 97)
		self.assertEqual(flt(rows[work_order.name]["process_loss_qty"]), 3)

	def test_cost_per_pack_is_reported_for_finished_goods(self):
		from frappe.desk.query_report import run

		sku = fixtures.ensure_item(f"CSKU {self.tag}", nature="Finished Good")
		frappe.db.set_value(
			"Item", sku, {"fm_bulk_item": self.blend, "fm_pack_size": 0.05, "fm_pack_uom": KG}
		)
		frappe.clear_document_cache("Item", sku)
		batch = self.receive(sku, 1000, 6, f"S-{self.tag}")

		result = run("FM Batch Cost", filters={"batch_no": batch}, ignore_prepared_report=True)
		row = next(r for r in result["result"] if r["batch_no"] == batch)
		self.assertEqual(flt(row["cost_per_pack"]), 6)
		self.assertEqual(flt(row["pack_size"]), 0.05)

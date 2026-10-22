"""The representative acceptance scenario, run for real against ERPNext stock.

    Consume 100 kg of ingredients (60 kg chilli + 40 kg cumin, identified lots)
    Produce 97 kg of usable blend
    Record 3 kg process loss
    Pack 50 kg into 1,000 packs of 50 g
    Pack 40 kg into 400 packs of 100 g
    Leave 7 kg in bulk stock
    Consume the appropriate pouches and cartons
    Trace both finished batches back to the actual supplier lots

Nothing here is simulated: real Work Orders and Stock Entries are posted, and
every number is read back from the stock ledger afterwards.
"""

import frappe
from frappe.utils import flt

from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.packaging.validation import get_packaging_variance
from food_manufacturing.production.genealogy import trace_backward
from food_manufacturing.tests import fixtures

KG = "Kg"
NOS = "Nos"


class TestAcceptanceScenario(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		fixtures.ensure_uom(KG)
		fixtures.ensure_uom(NOS)

	def setUp(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()

		self.original_batch_setting = frappe.db.get_single_value(
			"Stock Settings", "enable_serial_and_batch_no_for_item"
		)
		frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

		self.policy = fixtures.ensure_policy(
			self.site, require_incoming_inspection=0, yield_variance_tolerance_percent=5
		)

		tag = self._testMethodName.replace("test_", "")[:16]
		self.tag = tag
		self.chilli = fixtures.ensure_item(f"Chilli {tag}", nature="Raw Material")
		self.cumin = fixtures.ensure_item(f"Cumin {tag}", nature="Raw Material")
		self.blend = fixtures.ensure_item(f"Blend {tag}", nature="Bulk Blend")

		self.pouch50 = fixtures.ensure_item(f"Pouch50 {tag}", nature="Packaging Material",
		                                    has_batch=False, uom=NOS)
		self.pouch100 = fixtures.ensure_item(f"Pouch100 {tag}", nature="Packaging Material",
		                                     has_batch=False, uom=NOS)
		self.carton = fixtures.ensure_item(f"Carton {tag}", nature="Packaging Material",
		                                   has_batch=False, uom=NOS)

		self.sku50 = fixtures.ensure_item(f"SKU50g {tag}", nature="Finished Good")
		self.sku100 = fixtures.ensure_item(f"SKU100g {tag}", nature="Finished Good")
		for sku, pack_size in ((self.sku50, 0.05), (self.sku100, 0.1)):
			frappe.db.set_value(
				"Item",
				sku,
				{"fm_bulk_item": self.blend, "fm_pack_size": pack_size, "fm_pack_uom": KG},
			)
			frappe.clear_document_cache("Item", sku)

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

	def receive(self, item_code, qty, batch_id=None, status="Released"):
		row = {
			"item_code": item_code,
			"qty": qty,
			"t_warehouse": self.site["stores"],
			"basic_rate": 100,
		}
		batch = None
		if batch_id:
			batch = fixtures.ensure_batch(item_code, batch_id, status=status)
			row.update({"batch_no": batch, "use_serial_batch_fields": 1})

		doc = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"purpose": "Material Receipt",
				"company": self.site["company"],
				"items": [row],
			}
		)
		doc.insert()
		doc.submit()
		return batch

	def make_bom(self, item, quantity, uom, inputs):
		doc = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": item,
				"company": self.site["company"],
				"quantity": quantity,
				"uom": uom,
				"currency": frappe.get_cached_value(
					"Company", self.site["company"], "default_currency"
				),
				"is_active": 1,
				"is_default": 1,
				"items": [
					{"item_code": code, "qty": qty, "uom": input_uom}
					for code, qty, input_uom in inputs
				],
			}
		)
		doc.insert()
		doc.submit()
		return doc

	def run_work_order(self, item, bom, qty, fg_batch_id=None, process_loss_qty=0):
		from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

		work_order = frappe.get_doc(
			{
				"doctype": "Work Order",
				"production_item": item,
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
		work_order.insert()
		work_order.submit()

		produced_qty = flt(qty) - flt(process_loss_qty)
		entry = frappe.get_doc(make_stock_entry(work_order.name, "Manufacture", qty))

		fg_batch = fixtures.ensure_batch(item, fg_batch_id, status=None) if fg_batch_id else None
		for row in entry.items:
			row.use_serial_batch_fields = 1
			if fg_batch and row.item_code == item and row.t_warehouse:
				row.batch_no = fg_batch

		if process_loss_qty:
			entry.process_loss_qty = process_loss_qty
			for row in entry.items:
				if row.item_code == item and row.t_warehouse:
					row.qty = produced_qty
					row.transfer_qty = produced_qty

		entry.insert()
		entry.submit()
		work_order.reload()
		return work_order, entry, fg_batch

	def stock_in_stores(self, item_code, batch_no=None):
		filters = {
			"item_code": item_code,
			"warehouse": self.site["stores"],
			"is_cancelled": 0,
		}
		rows = frappe.get_all(
			"Stock Ledger Entry", filters=filters, fields=["actual_qty"], order_by="name asc"
		)
		return flt(sum(flt(r.actual_qty) for r in rows))

	# -- the scenario ---------------------------------------------------------

	# Split into two tests so a packaging failure is distinguishable from a
	# blending failure, while the packaging test runs the blend itself, so the
	# numbers are genuinely carried through rather than re-stated.

	def blend_97kg(self):
		"""Blending step: 100 kg in, 97 kg out, 3 kg process loss."""
		chilli_lot = self.receive(self.chilli, 60, f"CHILLI-{self.tag}")
		cumin_lot = self.receive(self.cumin, 40, f"CUMIN-{self.tag}")

		bom = self.make_bom(
			self.blend, 100, KG, [(self.chilli, 60, KG), (self.cumin, 40, KG)]
		)
		work_order, _entry, bulk_batch = self.run_work_order(
			self.blend, bom.name, 100, fg_batch_id=f"BULK-{self.tag}", process_loss_qty=3
		)
		return chilli_lot, cumin_lot, work_order, bulk_batch

	def test_blending_consumes_100kg_and_yields_97kg_with_3kg_loss(self):
		chilli_lot, cumin_lot, work_order, bulk_batch = self.blend_97kg()

		self.assertEqual(flt(work_order.produced_qty), 97)
		self.assertEqual(flt(work_order.process_loss_qty), 3)

		# Ingredients fully consumed, nothing left in stores.
		self.assertEqual(self.stock_in_stores(self.chilli), 0)
		self.assertEqual(self.stock_in_stores(self.cumin), 0)

		# 97 kg of bulk is on hand.
		self.assertEqual(self.stock_in_stores(self.blend), 97)

		# Loss is recorded as loss, not as a by-product.
		self.assertEqual(flt(work_order.fm_process_loss_qty_snapshot), 3)
		self.assertEqual(flt(work_order.fm_byproduct_qty), 0)
		self.assertEqual(work_order.fm_yield_basis, KG)
		self.assertEqual(flt(work_order.fm_actual_yield_percent), 97)
		self.assertEqual(work_order.fm_yield_flagged, 0)
		self.assertTrue(chilli_lot and cumin_lot and bulk_batch)

	def test_packing_into_two_sizes_leaves_7kg_of_bulk(self):
		chilli_lot, cumin_lot, _wo, bulk_batch = self.blend_97kg()

		self.receive(self.pouch50, 1000)
		self.receive(self.pouch100, 400)
		self.receive(self.carton, 60)

		# 1,000 packs of 50 g = 50 kg, plus one carton per 100 packs.
		bom50 = self.make_bom(
			self.sku50,
			1000,
			NOS,
			[(self.blend, 50, KG), (self.pouch50, 1000, NOS), (self.carton, 10, NOS)],
		)
		wo50, _e50, batch50 = self.run_work_order(
			self.sku50, bom50.name, 1000, fg_batch_id=f"SKU50-{self.tag}"
		)

		# 400 packs of 100 g = 40 kg.
		bom100 = self.make_bom(
			self.sku100,
			400,
			NOS,
			[(self.blend, 40, KG), (self.pouch100, 400, NOS), (self.carton, 4, NOS)],
		)
		wo100, _e100, batch100 = self.run_work_order(
			self.sku100, bom100.name, 400, fg_batch_id=f"SKU100-{self.tag}"
		)

		# Packs produced
		self.assertEqual(flt(wo50.produced_qty), 1000)
		self.assertEqual(flt(wo100.produced_qty), 400)
		self.assertEqual(self.stock_in_stores(self.sku50), 1000)
		self.assertEqual(self.stock_in_stores(self.sku100), 400)

		# 97 - 50 - 40 = 7 kg of bulk left, with no further packing loss.
		self.assertEqual(self.stock_in_stores(self.blend), 7)

		# Packaging consumed
		self.assertEqual(self.stock_in_stores(self.pouch50), 0)
		self.assertEqual(self.stock_in_stores(self.pouch100), 0)
		self.assertEqual(self.stock_in_stores(self.carton), 60 - 14)

		# Packaging variance is derived, and is zero when consumption matched.
		variance = {row["item_code"]: row for row in get_packaging_variance(wo50.name)}
		self.assertEqual(flt(variance[self.pouch50]["variance_qty"]), 0)
		self.assertEqual(flt(variance[self.carton]["variance_qty"]), 0)

		# Both finished batches trace back to the real supplier lots.
		for sku, batch in ((self.sku50, batch50), (self.sku100, batch100)):
			tree = trace_backward(sku, batch)
			leaves = self._leaf_batches(tree)
			self.assertIn(chilli_lot, leaves, msg=f"{sku} lost the chilli lot")
			self.assertIn(cumin_lot, leaves, msg=f"{sku} lost the cumin lot")
			self.assertIn(bulk_batch, self._all_batches(tree))

	def _leaf_batches(self, node) -> set:
		"""Batches with nothing producing them: the purchased lots."""
		if not node.get("inputs"):
			return {node["batch_no"]} if not node.get("work_orders") else set()

		found = set()
		for child in node["inputs"]:
			found |= self._leaf_batches(child)

		return found

	def _all_batches(self, node) -> set:
		found = {node["batch_no"]}
		for child in node.get("inputs") or []:
			found |= self._all_batches(child)

		return found

	# -- 5.5 ingredients cannot be consumed twice ----------------------------

	def test_packaging_bom_cannot_consume_raw_ingredients(self):
		"""The structural guard: no path consumes an ingredient twice."""
		bad_bom = self.make_bom(
			self.sku50,
			1000,
			NOS,
			[(self.blend, 50, KG), (self.chilli, 5, KG), (self.pouch50, 1000, NOS)],
		)

		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Work Order",
					"production_item": self.sku50,
					"bom_no": bad_bom.name,
					"qty": 1000,
					"company": self.site["company"],
					"fg_warehouse": self.site["stores"],
					"wip_warehouse": self.site["stores"],
					"source_warehouse": self.site["stores"],
					"use_multi_level_bom": 0,
					"skip_transfer": 1,
				}
			).insert()

	def test_packaging_bom_must_consume_the_declared_bulk_item(self):
		other_blend = fixtures.ensure_item(f"Other {self.tag}", nature="Bulk Blend")
		wrong_bom = self.make_bom(
			self.sku50,
			1000,
			NOS,
			[(other_blend, 50, KG), (self.pouch50, 1000, NOS)],
		)

		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Work Order",
					"production_item": self.sku50,
					"bom_no": wrong_bom.name,
					"qty": 1000,
					"company": self.site["company"],
					"fg_warehouse": self.site["stores"],
					"wip_warehouse": self.site["stores"],
					"source_warehouse": self.site["stores"],
					"use_multi_level_bom": 0,
					"skip_transfer": 1,
				}
			).insert()

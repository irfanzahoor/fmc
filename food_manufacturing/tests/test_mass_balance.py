"""Lot disposition and transformation balance, against real ERPNext stock.

Two of these are regression tests for bugs the demo data caught the first time
this module ran against it, and both were wrong in the same direction — they
invented material that did not exist:

* a quarantine-to-stores transfer was counted as a second receipt, so a 120 kg
  lot read as 240 kg received;
* a packaging step consuming kilograms of bulk to produce a count of packs was
  reported as "950 over", which is arithmetic on incompatible units.
"""

import frappe
from frappe.utils import flt

from food_manufacturing.compat.stock import get_lot_feature, set_lot_feature
from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.production.mass_balance import (
	get_chain_transformation,
	get_lot_disposition,
	get_mass_balance,
)
from food_manufacturing.tests import fixtures


class TestMassBalance(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		cls.kg = fixtures.ensure_uom("Kg")

	def setUp(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()

		self.original_batch_setting = get_lot_feature()
		set_lot_feature(1)

		self.policy = fixtures.ensure_policy(
			self.site, require_incoming_inspection=0, yield_variance_tolerance_percent=2
		)

		self.tag = self._testMethodName.replace("test_", "")[:24]
		self.blend = fixtures.ensure_item(f"Blend {self.tag}", nature="Bulk Blend")
		self.chilli = fixtures.ensure_item(f"Chilli {self.tag}", nature="Raw Material")
		self.cumin = fixtures.ensure_item(f"Cumin {self.tag}", nature="Raw Material")

	def tearDown(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		set_lot_feature(self.original_batch_setting)

	# -- helpers --------------------------------------------------------------

	def receive(self, item_code, qty, batch_id, warehouse=None):
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
						"t_warehouse": warehouse or self.site["stores"],
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

	def transfer(self, item_code, batch, qty, source, target):
		doc = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Transfer",
				"purpose": "Material Transfer",
				"company": self.site["company"],
				"items": [
					{
						"item_code": item_code,
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

	def manufacture(self, work_order, qty, batch_id, process_loss_qty=0, consumed=None):
		"""Submit a Manufacture Stock Entry for the whole ``qty`` of the order.

		The finished-goods row is set to ``qty - process_loss_qty``, the way
		ERPNext itself expresses a run that lost material: asking
		``make_stock_entry`` for the reduced quantity instead would scale the
		*consumption* down with it, and the input total is the thing these
		tests are measuring.

		``consumed`` overrides a raw material row's quantity, which is how an
		under-reported input is staged.
		"""
		from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

		entry = frappe.get_doc(make_stock_entry(work_order.name, "Manufacture", qty))
		fg_batch = fixtures.ensure_batch(self.blend, batch_id, status=None)
		for row in entry.items:
			row.use_serial_batch_fields = 1
			if row.item_code == self.blend and row.t_warehouse:
				row.batch_no = fg_batch
				row.qty = qty - process_loss_qty
				row.transfer_qty = qty - process_loss_qty
			elif consumed and row.item_code in consumed:
				row.qty = consumed[row.item_code]
				row.transfer_qty = consumed[row.item_code]

		if process_loss_qty:
			entry.process_loss_qty = process_loss_qty

		entry.insert()
		entry.submit()
		return entry

	def blend_run(self, qty=100, process_loss_qty=3, consumed=None):
		"""Receive, release and blend 60 kg chilli + 40 kg cumin."""
		chilli = self.receive(self.chilli, 60, f"LOT-CH-{self.tag}")
		cumin = self.receive(self.cumin, 40, f"LOT-CU-{self.tag}")
		self.release(chilli)
		self.release(cumin)
		order = self.make_work_order(self.approve_recipe().bom)
		self.manufacture(
			order, qty, f"BULK-{self.tag}", process_loss_qty=process_loss_qty, consumed=consumed
		)
		return chilli, cumin, order

	# -- disposition ----------------------------------------------------------

	def test_an_untouched_lot_is_all_on_hand(self):
		batch = self.receive(self.chilli, 80, f"LOT-IDLE-{self.tag}")

		row = get_lot_disposition(batch, self.site["company"])

		self.assertEqual(flt(row["received_qty"]), 80)
		self.assertEqual(flt(row["inward_qty"]), 80)
		self.assertEqual(flt(row["on_hand_qty"]), 80)
		self.assertEqual(flt(row["consumed_in_production"]), 0)
		self.assertEqual(flt(row["residual_qty"]), 0)
		self.assertEqual(row["stock_uom"], "Kg")

	def test_an_internal_transfer_is_not_a_second_receipt(self):
		"""Regression: a 120 kg lot moved quarantine->stores read as 240 kg in.

		Both legs of a transfer are in the ledger, one negative and one
		positive. Counting the positive leg invents material the plant never
		received, and it is the single easiest way to make a mass balance lie.
		"""
		batch = self.receive(self.chilli, 120, f"LOT-MOVE-{self.tag}", warehouse=self.site["quarantine"])
		self.transfer(self.chilli, batch, 120, self.site["quarantine"], self.site["stores"])

		row = get_lot_disposition(batch, self.site["company"])

		self.assertEqual(flt(row["received_qty"]), 120)
		self.assertEqual(flt(row["inward_qty"]), 120)
		self.assertEqual(flt(row["on_hand_qty"]), 120)
		self.assertEqual(flt(row["residual_qty"]), 0)

	def test_consumption_leaves_nothing_unaccounted(self):
		chilli, _cumin, _order = self.blend_run()

		row = get_lot_disposition(chilli, self.site["company"])

		self.assertEqual(flt(row["received_qty"]), 60)
		self.assertEqual(flt(row["consumed_in_production"]), 60)
		self.assertEqual(flt(row["on_hand_qty"]), 0)
		self.assertEqual(flt(row["residual_qty"]), 0)

	def test_a_manufactured_batch_is_produced_not_received(self):
		"""The two inward lines are kept apart: bought is not the same as made."""
		self.blend_run()
		bulk = f"{fixtures.PREFIX}-BULK-{self.tag}"

		row = get_lot_disposition(bulk, self.site["company"])

		self.assertEqual(flt(row["received_qty"]), 0)
		self.assertEqual(flt(row["produced_qty"]), 97)
		self.assertEqual(flt(row["inward_qty"]), 97)
		self.assertEqual(flt(row["on_hand_qty"]), 97)

	def test_rejected_stock_is_reported_as_already_contained(self):
		batch = self.receive(self.chilli, 50, f"LOT-REJ-{self.tag}", warehouse=self.site["quarantine"])
		self.transfer(self.chilli, batch, 50, self.site["quarantine"], self.site["rejected"])

		row = get_lot_disposition(batch, self.site["company"])

		self.assertEqual(flt(row["on_hand_qty"]), 50)
		self.assertEqual(flt(row["in_rejected_warehouse"]), 50)

	def test_disposition_names_every_warehouse_holding_the_lot(self):
		batch = self.receive(self.chilli, 100, f"LOT-SPLIT-{self.tag}", warehouse=self.site["quarantine"])
		self.transfer(self.chilli, batch, 40, self.site["quarantine"], self.site["stores"])

		row = get_lot_disposition(batch, self.site["company"])
		by_warehouse = {entry["warehouse"]: flt(entry["qty"]) for entry in row["on_hand_by_warehouse"]}

		self.assertEqual(by_warehouse.get(self.site["quarantine"]), 60)
		self.assertEqual(by_warehouse.get(self.site["stores"]), 40)

	def test_an_unknown_batch_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			get_lot_disposition(f"{fixtures.PREFIX}-NOT-A-BATCH", self.site["company"])

	# -- transformation -------------------------------------------------------

	def test_a_balanced_run_reports_no_overrun(self):
		chilli, _cumin, order = self.blend_run()

		steps = get_chain_transformation(chilli, self.site["company"])

		self.assertEqual([step["work_order"] for step in steps], [order.name])
		step = steps[0]
		self.assertTrue(step["comparable"])
		self.assertEqual(flt(step["lot_input_qty"]), 60)
		self.assertEqual(flt(step["total_input_qty"]), 100)
		self.assertEqual(flt(step["total_output_qty"]), 97)
		self.assertEqual(flt(step["process_loss_qty"]), 3)
		self.assertEqual(flt(step["overrun_qty"]), 0)
		self.assertFalse(step["flagged"])

	def test_output_above_input_is_flagged(self):
		"""90 kg of input cannot make 100 kg of blend.

		ERPNext will not let a run produce more than the order quantity, so an
		overrun is staged the way it actually reaches a plant's books: the
		output is right and the *input* is under-reported. 50 kg of chilli
		recorded instead of 60 leaves 90 kg in against 100 kg out.
		"""
		chilli, _cumin, _order = self.blend_run(
			process_loss_qty=0, consumed={self.chilli: 50}
		)

		steps = get_chain_transformation(chilli, self.site["company"])

		self.assertTrue(steps[0]["comparable"])
		self.assertEqual(flt(steps[0]["total_input_qty"]), 90)
		self.assertEqual(flt(steps[0]["total_output_qty"]), 100)
		self.assertEqual(flt(steps[0]["overrun_qty"]), 10)
		self.assertTrue(steps[0]["flagged"])
		self.assertTrue(get_mass_balance(chilli, self.site["company"])["flagged"])

	def test_a_loss_within_tolerance_is_not_flagged(self):
		chilli, _cumin, _order = self.blend_run(process_loss_qty=10)

		steps = get_chain_transformation(chilli, self.site["company"])

		self.assertEqual(flt(steps[0]["overrun_qty"]), 0)
		self.assertFalse(steps[0]["flagged"])

	def test_a_step_in_mixed_units_is_not_compared(self):
		"""Regression: kg of bulk against a count of packs is not a balance.

		``yield_tracking`` refuses the same arithmetic for the same reason. A
		packaging step must report its figures and say why they cannot be
		subtracted, rather than producing a number nobody should trust.
		"""
		chilli, _cumin, _order = self.blend_run()
		bulk = f"{fixtures.PREFIX}-BULK-{self.tag}"
		# A manufactured batch starts in Quarantine under the default policy, so
		# the packaging run cannot consume it until it has its own decision.
		self.release(bulk)

		pack = fixtures.ensure_item(f"Pack {self.tag}", nature="Finished Good", uom="Nos")
		frappe.db.set_value("Item", pack, "fm_bulk_item", self.blend)
		bom = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": pack,
				"quantity": 1000,
				"company": self.site["company"],
				# Named explicitly, not left to default: the discovered company's
				# currency is whatever the site has, and a submitted BOM refuses
				# a currency that disagrees with its rates. Valuation Rate keeps
				# the costing off a price list this site may not have.
				"currency": frappe.get_cached_value(
					"Company", self.site["company"], "default_currency"
				),
				"rm_cost_as_per": "Valuation Rate",
				"items": [{"item_code": self.blend, "qty": 50, "uom": self.kg, "stock_uom": self.kg}],
			}
		)
		bom.insert()
		bom.submit()

		order = frappe.get_doc(
			{
				"doctype": "Work Order",
				"production_item": pack,
				"bom_no": bom.name,
				"qty": 1000,
				"company": self.site["company"],
				"fg_warehouse": self.site["stores"],
				"wip_warehouse": self.site["stores"],
				"source_warehouse": self.site["stores"],
				"use_multi_level_bom": 0,
				"skip_transfer": 1,
			}
		)
		order.insert()
		for row in order.required_items:
			row.source_warehouse = self.site["stores"]
		order.save()
		order.submit()

		from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

		entry = frappe.get_doc(make_stock_entry(order.name, "Manufacture", 1000))
		pack_batch = fixtures.ensure_batch(pack, f"PACK-{self.tag}", status=None)
		for row in entry.items:
			row.use_serial_batch_fields = 1
			if row.item_code == pack and row.t_warehouse:
				row.batch_no = pack_batch
		entry.insert()
		entry.submit()

		steps = get_chain_transformation(bulk, self.site["company"])
		step = next(row for row in steps if row["work_order"] == order.name)

		self.assertFalse(step["comparable"])
		self.assertIsNone(step["overrun_qty"])
		self.assertFalse(step["flagged"])
		self.assertIn("different units", step["balance_basis"])
		# The quantities are still reported - refusing to subtract them is not
		# a reason to hide them.
		self.assertEqual(flt(step["total_input_qty"]), 50)
		self.assertEqual(flt(step["total_output_qty"]), 1000)

	def test_a_lot_that_fed_nothing_has_no_steps(self):
		batch = self.receive(self.chilli, 10, f"LOT-NONE-{self.tag}")

		self.assertEqual(get_chain_transformation(batch, self.site["company"]), [])

	def test_mass_balance_combines_both_halves(self):
		chilli, _cumin, order = self.blend_run()

		result = get_mass_balance(chilli, self.site["company"])

		self.assertEqual(result["disposition"]["batch_no"], chilli)
		self.assertEqual([step["work_order"] for step in result["transformation"]], [order.name])
		self.assertFalse(result["flagged"])
		self.assertFalse(result["residual_material"])

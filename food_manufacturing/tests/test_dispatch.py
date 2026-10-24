"""Dispatch gating and recall tracing, against real Delivery Notes."""

import frappe
from frappe.utils import add_days, flt, today

from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.production.genealogy import trace_forward
from food_manufacturing.tests import fixtures


class TestDispatch(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		fixtures.ensure_uom("Kg")
		cls.customer = frappe.db.get_value("Customer", {}, "name")

	def setUp(self):
		if not self.customer:
			self.skipTest("Site has no Customer")

		fixtures.cleanup()
		self.original_batch_setting = frappe.db.get_single_value(
			"Stock Settings", "enable_serial_and_batch_no_for_item"
		)
		frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

		tag = self._testMethodName.replace("test_", "")[:16]
		self.tag = tag
		self.item = fixtures.ensure_item(f"Disp {tag}", nature="Finished Good")
		self.policy = fixtures.ensure_policy(self.site, min_remaining_shelf_life_percent=25)

	def tearDown(self):
		fixtures.cleanup()
		frappe.db.set_single_value(
			"Stock Settings",
			"enable_serial_and_batch_no_for_item",
			self.original_batch_setting,
		)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

	def stock_batch(self, batch_id, qty=10, expiry=None, manufactured=None, status="Released"):
		"""Receive stock, then set the batch's real dates.

		ERPNext refuses to *receive* stock into an already-expired batch, so the
		receipt happens while the batch is still valid and the dates are applied
		afterwards - which is what actually happens as stock ages on the shelf.
		"""
		batch = fixtures.ensure_batch(self.item, batch_id, status=status)

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

		values = {}
		if expiry:
			values["expiry_date"] = expiry
		if manufactured:
			values["manufacturing_date"] = manufactured
		if values:
			frappe.db.set_value("Batch", batch, values)
			frappe.clear_document_cache("Batch", batch)

		return batch

	def deliver(self, batch, qty=1, submit=False):
		doc = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": self.site["company"],
				"customer": self.customer,
				"items": [
					{
						"item_code": self.item,
						"qty": qty,
						"rate": 500,
						"warehouse": self.site["stores"],
						"batch_no": batch,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		doc.insert()
		if submit:
			doc.submit()

		return doc

	def take_back(self, delivery_note, submit=True):
		"""The customer return of a delivery: negative quantities, same batch."""
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_return

		doc = frappe.get_doc(make_sales_return(delivery_note))
		for row in doc.items:
			row.use_serial_batch_fields = 1

		doc.insert()
		if submit:
			doc.submit()

		return doc

	# -- a return is stock coming back, not a dispatch ------------------------

	def test_a_held_batch_can_still_be_returned(self):
		"""The case a recall depends on.

		Every outward rule used to run on a return as well, because a return is
		a Delivery Note and the row carried a warehouse. So the moment a batch
		was put on Hold - which is exactly what a recall does - the customer
		could no longer send it back, and the stock stayed recorded as out
		there. Quantity, not document type, says which way stock is moving.
		"""
		batch = self.stock_batch(f"RET-{self.tag}", qty=10)
		delivered = self.deliver(batch, qty=4, submit=True)

		frappe.db.set_value("Batch", batch, "fm_quality_status", "Hold")
		frappe.clear_document_cache("Batch", batch)

		returned = self.take_back(delivered.name)
		self.assertEqual(flt(returned.items[0].qty), -4)

	def test_a_rejected_batch_can_still_be_returned(self):
		batch = self.stock_batch(f"RETREJ-{self.tag}", qty=10)
		delivered = self.deliver(batch, qty=2, submit=True)

		frappe.db.set_value("Batch", batch, "fm_quality_status", "Rejected")
		frappe.clear_document_cache("Batch", batch)

		self.assertTrue(self.take_back(delivered.name).name)

	def test_a_batch_below_minimum_shelf_life_can_still_be_returned(self):
		"""The shelf-life rule needs the same direction check as the quality one.

		The stock ships while it is fresh and comes back when it is not, which
		is the ordinary way a return happens.
		"""
		batch = self.stock_batch(f"RETNEAR-{self.tag}", qty=10)
		delivered = self.deliver(batch, qty=3, submit=True)

		frappe.db.set_value(
			"Batch",
			batch,
			{"manufacturing_date": add_days(today(), -360), "expiry_date": add_days(today(), 4)},
		)
		frappe.clear_document_cache("Batch", batch)

		self.assertTrue(self.take_back(delivered.name).name)

	def test_a_return_is_not_judged_against_fefo(self):
		"""Which batch a customer sends back is their doing, not a pick.

		Unlike the quality and shelf-life rules, FEFO already ignored a return:
		its breach comparison skips any row whose quantity is not positive. This
		pins that down rather than fixing it - the rule is one refactor of that
		comparison away from blocking returns like the other two did.
		"""
		later = self.stock_batch(f"RETFEFO-{self.tag}", qty=10, expiry=add_days(today(), 300))
		delivered = self.deliver(later, qty=2, submit=True)

		# An earlier-expiring batch arrives afterwards, and FEFO turns strict.
		self.stock_batch(f"RETFEFOE-{self.tag}", qty=10, expiry=add_days(today(), 20))
		fixtures.ensure_policy(
			self.site, enforce_fefo="Block", min_remaining_shelf_life_percent=0
		)

		self.assertTrue(self.take_back(delivered.name).name)

	# -- 6.2 / 6.4 expiry and shelf life -------------------------------------

	def test_expired_batch_cannot_be_dispatched(self):
		batch = self.stock_batch(
			f"EXPIRED-{self.tag}",
			expiry=add_days(today(), -1),
			manufactured=add_days(today(), -365),
		)
		with self.assertRaises(frappe.ValidationError):
			self.deliver(batch)

	def test_erpnext_blocks_expired_dispatch_even_when_our_policy_permits(self):
		"""A limitation worth knowing, not a bug.

		ERPNext raises its own BatchExpiredError on a Delivery Note, below our
		hook, so setting ``block_expired_dispatch = 0`` does **not** make
		expired dispatch possible. The policy flag can only ever be stricter
		than ERPNext, never more permissive. Recorded in docs/acceptance.md.
		"""
		from erpnext.exceptions import BatchExpiredError

		fixtures.ensure_policy(
			self.site, block_expired_dispatch=0, min_remaining_shelf_life_percent=0
		)
		batch = self.stock_batch(
			f"EXPIRED-{self.tag}",
			expiry=add_days(today(), -1),
			manufactured=add_days(today(), -365),
		)
		with self.assertRaises(BatchExpiredError):
			self.deliver(batch)

	def test_batch_below_minimum_shelf_life_is_blocked(self):
		"""10% of shelf life left against a 25% floor."""
		batch = self.stock_batch(
			f"NEAR-{self.tag}",
			expiry=add_days(today(), 36),
			manufactured=add_days(today(), -324),
		)
		with self.assertRaises(frappe.ValidationError):
			self.deliver(batch)

	def test_batch_above_minimum_shelf_life_is_allowed(self):
		batch = self.stock_batch(
			f"FRESH-{self.tag}",
			expiry=add_days(today(), 300),
			manufactured=add_days(today(), -60),
		)
		self.deliver(batch)  # must not raise

	def test_shelf_life_floor_of_zero_disables_the_check(self):
		fixtures.ensure_policy(self.site, min_remaining_shelf_life_percent=0)
		batch = self.stock_batch(
			f"NEAR-{self.tag}",
			expiry=add_days(today(), 10),
			manufactured=add_days(today(), -350),
		)
		self.deliver(batch)  # must not raise

	def test_batch_without_expiry_is_not_shelf_life_managed(self):
		batch = self.stock_batch(f"NOEXP-{self.tag}")
		self.deliver(batch)  # must not raise

	def test_unknown_total_shelf_life_still_blocks_when_expired(self):
		"""No manufacturing date, so no percentage - but expiry still applies."""
		batch = self.stock_batch(f"NOMFG-{self.tag}", expiry=add_days(today(), -5))
		with self.assertRaises(frappe.ValidationError):
			self.deliver(batch)

	def test_held_batch_cannot_be_dispatched(self):
		batch = self.stock_batch(
			f"HELD-{self.tag}", expiry=add_days(today(), 300),
			manufactured=add_days(today(), -60), status="Hold",
		)
		with self.assertRaises(frappe.ValidationError):
			self.deliver(batch)

	def test_rule_holds_on_the_api_path(self):
		from frappe.client import insert

		batch = self.stock_batch(
			f"EXPIRED-{self.tag}",
			expiry=add_days(today(), -1),
			manufactured=add_days(today(), -365),
		)
		with self.assertRaises(frappe.ValidationError):
			insert(
				{
					"doctype": "Delivery Note",
					"company": self.site["company"],
					"customer": self.customer,
					"items": [
						{
							"item_code": self.item,
							"qty": 1,
							"rate": 500,
							"warehouse": self.site["stores"],
							"batch_no": batch,
							"use_serial_batch_fields": 1,
						}
					],
				}
			)

	# -- 6.3 FEFO enforcement modes ------------------------------------------

	def test_fefo_block_refuses_a_later_expiring_batch(self):
		fixtures.ensure_policy(
			self.site, enforce_fefo="Block", min_remaining_shelf_life_percent=0
		)
		self.stock_batch(
			f"SOON-{self.tag}", expiry=add_days(today(), 30),
			manufactured=add_days(today(), -30),
		)
		later = self.stock_batch(
			f"LATER-{self.tag}", expiry=add_days(today(), 300),
			manufactured=add_days(today(), -30),
		)
		with self.assertRaises(frappe.ValidationError):
			self.deliver(later)

	def test_fefo_block_allows_the_earliest_expiring_batch(self):
		fixtures.ensure_policy(
			self.site, enforce_fefo="Block", min_remaining_shelf_life_percent=0
		)
		soon = self.stock_batch(
			f"SOON-{self.tag}", expiry=add_days(today(), 30),
			manufactured=add_days(today(), -30),
		)
		self.stock_batch(
			f"LATER-{self.tag}", expiry=add_days(today(), 300),
			manufactured=add_days(today(), -30),
		)
		self.deliver(soon)  # must not raise

	def test_fefo_off_permits_any_batch(self):
		fixtures.ensure_policy(
			self.site, enforce_fefo="Off", min_remaining_shelf_life_percent=0
		)
		self.stock_batch(
			f"SOON-{self.tag}", expiry=add_days(today(), 30),
			manufactured=add_days(today(), -30),
		)
		later = self.stock_batch(
			f"LATER-{self.tag}", expiry=add_days(today(), 300),
			manufactured=add_days(today(), -30),
		)
		self.deliver(later)  # must not raise

	def test_fefo_warn_permits_but_messages(self):
		fixtures.ensure_policy(
			self.site, enforce_fefo="Warn", min_remaining_shelf_life_percent=0
		)
		self.stock_batch(
			f"SOON-{self.tag}", expiry=add_days(today(), 30),
			manufactured=add_days(today(), -30),
		)
		later = self.stock_batch(
			f"LATER-{self.tag}", expiry=add_days(today(), 300),
			manufactured=add_days(today(), -30),
		)
		frappe.clear_messages()
		self.deliver(later)  # must not raise
		messages = " ".join(str(m) for m in frappe.get_message_log())
		self.assertIn("FEFO", messages)

	# -- 6.6 / 6.8 recall tracing --------------------------------------------

	def test_forward_trace_reaches_the_customer(self):
		batch = self.stock_batch(
			f"SOLD-{self.tag}", qty=10, expiry=add_days(today(), 300),
			manufactured=add_days(today(), -60),
		)
		note = self.deliver(batch, qty=4, submit=True)

		shipments = trace_forward(self.item, batch)
		by_note = {s["delivery_note"]: s for s in shipments}
		self.assertIn(note.name, by_note)
		self.assertEqual(by_note[note.name]["customer"], self.customer)
		self.assertEqual(flt(by_note[note.name]["qty"]), 4)

	def test_forward_trace_ignores_other_batches(self):
		sold = self.stock_batch(
			f"SOLD-{self.tag}", expiry=add_days(today(), 300),
			manufactured=add_days(today(), -60),
		)
		unsold = self.stock_batch(
			f"UNSOLD-{self.tag}", expiry=add_days(today(), 310),
			manufactured=add_days(today(), -60),
		)
		self.deliver(sold, qty=1, submit=True)

		self.assertEqual(trace_forward(self.item, unsold), [])

	def test_cancelled_delivery_drops_out_of_the_trace(self):
		"""Cancellations must not leave a phantom shipment in a recall."""
		batch = self.stock_batch(
			f"SOLD-{self.tag}", expiry=add_days(today(), 300),
			manufactured=add_days(today(), -60),
		)
		note = self.deliver(batch, qty=2, submit=True)
		self.assertTrue(trace_forward(self.item, batch))

		note.cancel()
		self.assertEqual(trace_forward(self.item, batch), [])

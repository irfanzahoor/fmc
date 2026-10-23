"""Acceptance examples for the recall investigation.

The trace itself (forward, backward, bundles, cancellations) is covered by
`test_api.py` and `test_operator_guards_unit.py`. This file covers what Phase 4
added: **where the affected stock still is**, and the Desk report that an
investigation actually gets printed from.
"""

import frappe
from frappe.utils import flt

from food_manufacturing.api.recall import get_recall
from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.food_manufacturing_quality.report.fm_recall_investigation import (
	fm_recall_investigation as report,
)
from food_manufacturing.tests import fixtures


class TestRecallInvestigation(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()

	def setUp(self):
		fixtures.cleanup()
		fixtures.cleanup_users()

		self.original = frappe.db.get_single_value(
			"Stock Settings", "enable_serial_and_batch_no_for_item"
		)
		frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

		self.tag = self._testMethodName.replace("test_", "")[:12]
		self.policy = fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		self.chilli = fixtures.ensure_item(f"ARecChilli {self.tag}", nature="Raw Material")
		self.batch = fixtures.ensure_batch(self.chilli, f"REC-{self.tag}", status="Released")

	def tearDown(self):
		frappe.set_user("Administrator")
		fixtures.cleanup()
		fixtures.cleanup_users()
		frappe.db.set_single_value(
			"Stock Settings", "enable_serial_and_batch_no_for_item", self.original
		)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

	def receive(self, qty, warehouse=None):
		doc = frappe.get_doc({
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"purpose": "Material Receipt",
			"company": self.site["company"],
			"items": [{
				"item_code": self.chilli, "qty": qty,
				"t_warehouse": warehouse or self.site["stores"], "basic_rate": 100,
				"batch_no": self.batch, "use_serial_batch_fields": 1,
			}],
		})
		doc.insert()
		doc.submit()
		return doc

	def transfer(self, qty, source, target):
		doc = frappe.get_doc({
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Transfer",
			"purpose": "Material Transfer",
			"company": self.site["company"],
			"items": [{
				"item_code": self.chilli, "qty": qty,
				"s_warehouse": source, "t_warehouse": target,
				"batch_no": self.batch, "use_serial_batch_fields": 1,
			}],
		})
		doc.insert()
		doc.submit()
		return doc

	# --- affected stock -----------------------------------------------------

	def test_the_investigation_says_where_the_stock_is(self):
		"""You cannot quarantine what you cannot locate."""
		self.receive(60)

		result = get_recall(self.batch, self.site["company"])
		on_hand = result["on_hand"]

		self.assertEqual(len(on_hand), 1)
		self.assertEqual(on_hand[0]["warehouse"], self.site["stores"])
		self.assertAlmostEqual(flt(on_hand[0]["qty"]), 60.0, places=2)

	def test_a_split_lot_is_reported_in_every_warehouse_it_sits_in(self):
		self.receive(100)
		self.transfer(40, self.site["stores"], self.site["quarantine"])

		on_hand = {
			row["warehouse"]: flt(row["qty"])
			for row in get_recall(self.batch, self.site["company"])["on_hand"]
		}

		self.assertAlmostEqual(on_hand[self.site["stores"]], 60.0, places=2)
		self.assertAlmostEqual(on_hand[self.site["quarantine"]], 40.0, places=2)

	def test_a_warehouse_holding_none_of_it_is_not_listed(self):
		"""An empty warehouse is not a place to go and look."""
		self.receive(50)
		self.transfer(50, self.site["stores"], self.site["quarantine"])

		warehouses = {row["warehouse"] for row in get_recall(self.batch, self.site["company"])["on_hand"]}

		self.assertNotIn(self.site["stores"], warehouses)
		self.assertIn(self.site["quarantine"], warehouses)

	def test_on_hand_is_read_from_the_ledger_not_the_batch_field(self):
		"""Batch.batch_qty does not survive a part-consumed, split lot."""
		self.receive(100)
		self.transfer(30, self.site["stores"], self.site["rejected"])

		total = sum(flt(row["qty"]) for row in get_recall(self.batch, self.site["company"])["on_hand"])
		self.assertAlmostEqual(total, 100.0, places=2)

	# --- the Desk report ----------------------------------------------------

	def test_the_report_needs_a_batch_and_a_company(self):
		columns, rows, message = report.execute({})

		self.assertTrue(columns)
		self.assertEqual(rows, [])
		self.assertIn("Choose a batch", message)

	def test_the_report_lists_the_batch_and_its_stock(self):
		self.receive(75)

		_columns, rows, _message = report.execute(
			{"batch": self.batch, "company": self.site["company"]}
		)

		sections = {row["section"] for row in rows}
		self.assertIn("Affected batch", sections)
		self.assertIn("Stock on hand", sections)

		stock = next(row for row in rows if row["section"] == "Stock on hand")
		self.assertEqual(stock["warehouse"], self.site["stores"])
		self.assertAlmostEqual(flt(stock["qty"]), 75.0, places=2)

	def test_the_report_can_be_narrowed_to_one_section(self):
		self.receive(20)

		_columns, rows, _message = report.execute({
			"batch": self.batch, "company": self.site["company"], "section": "Stock on hand",
		})

		self.assertTrue(rows)
		self.assertEqual({row["section"] for row in rows}, {"Stock on hand"})

	def test_the_report_states_that_nobody_was_notified(self):
		"""Telling customers is a decision with legal weight, not a side effect."""
		self.receive(10)

		_columns, _rows, message = report.execute(
			{"batch": self.batch, "company": self.site["company"]}
		)

		self.assertIn("No customer has been notified", message)

	def test_the_report_says_when_the_trace_was_cut_short(self):
		self.receive(10)

		_columns, _rows, message = report.execute(
			{"batch": self.batch, "company": self.site["company"]}
		)

		# This trace is shallow, so it must NOT claim to be truncated.
		self.assertNotIn("cut short", message)

	# --- permissions --------------------------------------------------------

	def test_a_user_without_batch_access_is_refused(self):
		self.receive(10)
		user = fixtures.ensure_user("recnobody", ())
		frappe.set_user(user)

		with self.assertRaises(frappe.PermissionError):
			get_recall(self.batch, self.site["company"])

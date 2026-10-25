"""Recorded recall exercises.

The drill has to use the same trace a real investigation uses, so these assert
on figures produced by `api/recall.get_recall` rather than on anything the
drill computes for itself. What is tested here is the *recording*: that the
result is pinned at the moment it was taken, that an incomplete trace is
recorded as incomplete rather than quietly rounded to a pass, and that signing
is a separate act from running.
"""

import json

import frappe
from frappe.utils import flt

from food_manufacturing.api.drill import get_drill_history, run_recall_drill
from food_manufacturing.compat.stock import get_lot_feature, set_lot_feature
from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.tests import fixtures


class TestRecallDrill(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		cls.kg = fixtures.ensure_uom("Kg")

	def setUp(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		fixtures.cleanup_users()

		self.original_batch_setting = get_lot_feature()
		set_lot_feature(1)

		self.policy = fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		self.tag = self._testMethodName.replace("test_", "")[:24]
		self.chilli = fixtures.ensure_item(f"Chilli {self.tag}", nature="Raw Material")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete("FM Recall Drill", {"company": self.site["company"]})
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		fixtures.cleanup_users()
		set_lot_feature(self.original_batch_setting)

	# -- helpers --------------------------------------------------------------

	def receive(self, qty, batch_id):
		batch = fixtures.ensure_batch(self.chilli, batch_id, status=None)
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

	# -- running --------------------------------------------------------------

	def test_a_drill_records_the_trace_and_stays_in_draft(self):
		"""Running is not signing: the record is left for a person to submit."""
		batch = self.receive(40, f"LOT-D1-{self.tag}")

		result = run_recall_drill(batch, self.site["company"], "Mock Drill", "Quarterly exercise.")

		doc = frappe.get_doc("FM Recall Drill", result["name"])
		self.assertEqual(doc.docstatus, 0)
		self.assertEqual(doc.drill_type, "Mock Drill")
		self.assertEqual(doc.item_code, self.chilli)
		self.assertEqual(doc.findings, "Quarterly exercise.")
		self.assertEqual(flt(doc.inward_qty), 40)
		self.assertEqual(flt(doc.on_hand_qty), 40)
		self.assertEqual(flt(doc.accounted_percent), 100)
		self.assertTrue(doc.trace_complete)
		self.assertFalse(doc.balance_flagged)

	def test_the_elapsed_time_is_recorded(self):
		"""The figure an auditor asks for, and it must be real, not blank."""
		batch = self.receive(10, f"LOT-D2-{self.tag}")

		result = run_recall_drill(batch, self.site["company"])

		self.assertGreater(flt(result["seconds_to_trace"]), 0)
		self.assertLess(flt(result["seconds_to_trace"]), 120)

	def test_the_snapshot_holds_the_trace_as_it_read(self):
		batch = self.receive(25, f"LOT-D3-{self.tag}")

		doc = frappe.get_doc("FM Recall Drill", run_recall_drill(batch, self.site["company"])["name"])
		snapshot = json.loads(doc.trace_snapshot)

		self.assertIn("trace", snapshot)
		self.assertIn("balance", snapshot)
		self.assertEqual(
			[row["name"] for row in snapshot["trace"]["batches"]],
			[batch],
		)
		self.assertEqual(flt(snapshot["balance"]["disposition"]["inward_qty"]), 25)

	def test_the_snapshot_does_not_change_when_the_stock_moves_on(self):
		"""The whole reason the result is stored rather than re-derived.

		An auditor asks what the drill found on the day. If the record answered
		with today's position instead, it would not be evidence of anything.
		"""
		batch = self.receive(30, f"LOG-D4-{self.tag}")
		doc = frappe.get_doc("FM Recall Drill", run_recall_drill(batch, self.site["company"])["name"])
		doc.submit()

		# Consume the lot after the drill was filed.
		issue = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Issue",
				"purpose": "Material Issue",
				"company": self.site["company"],
				"items": [
					{
						"item_code": self.chilli,
						"qty": 30,
						"s_warehouse": self.site["stores"],
						"batch_no": batch,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		issue.insert()
		issue.submit()

		doc.reload()
		self.assertEqual(flt(doc.on_hand_qty), 30)
		self.assertEqual(flt(json.loads(doc.trace_snapshot)["balance"]["disposition"]["on_hand_qty"]), 30)

	def test_an_unknown_drill_type_is_refused(self):
		batch = self.receive(10, f"LOT-D5-{self.tag}")

		with self.assertRaises(frappe.ValidationError):
			run_recall_drill(batch, self.site["company"], "Fire Drill")

	def test_a_batch_with_no_history_here_is_refused(self):
		"""A drill reporting zeroes for a lot this company never held reads as a pass."""
		batch = fixtures.ensure_batch(self.chilli, f"LOT-D6-{self.tag}", status=None)

		with self.assertRaises(frappe.ValidationError):
			run_recall_drill(batch, self.site["company"])

	# -- signing --------------------------------------------------------------

	def test_submitting_names_the_person_who_signed(self):
		batch = self.receive(15, f"LOT-D7-{self.tag}")
		doc = frappe.get_doc("FM Recall Drill", run_recall_drill(batch, self.site["company"])["name"])

		doc.submit()

		self.assertEqual(doc.docstatus, 1)
		self.assertEqual(doc.conducted_by, "Administrator")

	def test_a_drill_without_a_trace_cannot_be_submitted(self):
		"""A hand-made record is not evidence; it has to have been run."""
		batch = self.receive(15, f"LOT-D8-{self.tag}")
		doc = frappe.get_doc(
			{
				"doctype": "FM Recall Drill",
				"batch": batch,
				"company": self.site["company"],
				"drill_type": "Mock Drill",
			}
		)
		doc.insert()

		with self.assertRaises(frappe.ValidationError):
			doc.submit()

	# -- history --------------------------------------------------------------

	def test_history_returns_submitted_drills_newest_first(self):
		first = self.receive(10, f"LOT-D9A-{self.tag}")
		second = self.receive(10, f"LOT-D9B-{self.tag}")
		for batch in (first, second):
			frappe.get_doc(
				"FM Recall Drill", run_recall_drill(batch, self.site["company"])["name"]
			).submit()

		history = get_drill_history(self.site["company"])

		self.assertEqual([row["batch"] for row in history][:2], [second, first])

	def test_history_leaves_out_drafts(self):
		batch = self.receive(10, f"LOT-D10-{self.tag}")
		run_recall_drill(batch, self.site["company"])

		self.assertEqual(get_drill_history(self.site["company"]), [])

	# -- permissions ----------------------------------------------------------

	def test_running_a_drill_needs_create_rights(self):
		"""A drill reads the whole downstream customer list, so it is gated."""
		batch = self.receive(10, f"LOT-D11-{self.tag}")
		operator = fixtures.ensure_user("operator", ("FM Production Operator",))
		frappe.set_user(operator)

		with self.assertRaises(frappe.PermissionError):
			run_recall_drill(batch, self.site["company"])

	def test_the_endpoint_is_post_only(self):
		"""A drill writes a record, so it must not be reachable by GET."""
		self.assertEqual(
			frappe.allowed_http_methods_for_whitelisted_func.get(run_recall_drill),
			["POST"],
		)

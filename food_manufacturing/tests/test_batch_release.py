"""FM Batch Release: authorisation, transitions, audit and idempotency."""

import frappe

from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.tests import fixtures


class TestFMBatchRelease(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()

	def setUp(self):
		fixtures.cleanup()
		self.policy = fixtures.ensure_policy(self.site)
		self.item = fixtures.ensure_item("Chilli", nature="Raw Material")

	def tearDown(self):
		fixtures.cleanup()

	def make_release(self, batch, decision="Release", submit=False, **overrides):
		values = {
			"doctype": "FM Batch Release",
			"batch": batch,
			"company": self.site["company"],
			"decision": decision,
		}
		if decision != "Release":
			values["reason"] = "Out of specification"
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert()
		if submit:
			doc.submit()

		return doc

	def status_of(self, batch):
		return frappe.db.get_value("Batch", batch, "fm_quality_status")

	# -- release requires an inspection when policy says so ------------------

	def test_release_blocked_without_inspection_when_required(self):
		batch = fixtures.ensure_batch(self.item, "A1", status="Quarantine")
		with self.assertRaises(frappe.ValidationError):
			self.make_release(batch, submit=True)

	def test_release_allowed_without_inspection_when_policy_relaxed(self):
		fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		batch = fixtures.ensure_batch(self.item, "A2", status="Quarantine")
		self.make_release(batch, submit=True)
		self.assertEqual(self.status_of(batch), "Released")

	# -- decisions and audit trail -------------------------------------------

	def test_reject_sets_status_and_records_reason(self):
		batch = fixtures.ensure_batch(self.item, "A3", status="Quarantine")
		doc = self.make_release(batch, decision="Reject", submit=True)
		self.assertEqual(self.status_of(batch), "Rejected")
		self.assertEqual(doc.previous_status, "Quarantine")
		self.assertTrue(doc.reason)

	def test_hold_sets_status(self):
		batch = fixtures.ensure_batch(self.item, "A4", status="Quarantine")
		self.make_release(batch, decision="Hold", submit=True)
		self.assertEqual(self.status_of(batch), "Hold")

	def test_reason_mandatory_for_hold_and_reject(self):
		batch = fixtures.ensure_batch(self.item, "A5", status="Quarantine")
		for decision in ("Hold", "Reject"):
			with self.subTest(decision=decision):
				doc = frappe.get_doc(
					{
						"doctype": "FM Batch Release",
						"batch": batch,
						"company": self.site["company"],
						"decision": decision,
					}
				)
				with self.assertRaises(frappe.ValidationError):
					doc.insert()

	def test_decision_records_who_authorised_it(self):
		fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		batch = fixtures.ensure_batch(self.item, "A6", status="Quarantine")
		doc = self.make_release(batch, submit=True)
		self.assertEqual(doc.decided_by, frappe.session.user)
		self.assertEqual(frappe.db.get_value("Batch", batch, "fm_released_by"), frappe.session.user)
		self.assertEqual(frappe.db.get_value("Batch", batch, "fm_last_release"), doc.name)

	# -- transitions ----------------------------------------------------------

	def test_rejected_is_terminal(self):
		fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		batch = fixtures.ensure_batch(self.item, "A7", status="Rejected")
		with self.assertRaises(frappe.ValidationError):
			self.make_release(batch, submit=True)

	def test_held_batch_can_be_released(self):
		fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		batch = fixtures.ensure_batch(self.item, "A8", status="Hold")
		self.make_release(batch, submit=True)
		self.assertEqual(self.status_of(batch), "Released")

	def test_released_batch_can_be_recalled_to_hold(self):
		fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		batch = fixtures.ensure_batch(self.item, "A9", status="Released")
		self.make_release(batch, decision="Hold", submit=True)
		self.assertEqual(self.status_of(batch), "Hold")

	def test_disabled_batch_cannot_be_decided(self):
		batch = fixtures.ensure_batch(self.item, "A10", status="Quarantine")
		frappe.db.set_value("Batch", batch, "disabled", 1)
		with self.assertRaises(frappe.ValidationError):
			self.make_release(batch)

	# -- idempotency and cancellation ----------------------------------------

	def test_duplicate_release_is_rejected(self):
		"""A retried release must not silently succeed twice."""
		fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		batch = fixtures.ensure_batch(self.item, "A11", status="Quarantine")
		self.make_release(batch, submit=True)

		# Second, independently drafted release of the same batch.
		with self.assertRaises(frappe.ValidationError):
			self.make_release(batch, submit=True)

		self.assertEqual(self.status_of(batch), "Released")

	def test_cancel_restores_previous_status(self):
		fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		batch = fixtures.ensure_batch(self.item, "A12", status="Quarantine")
		doc = self.make_release(batch, submit=True)
		self.assertEqual(self.status_of(batch), "Released")

		doc.cancel()
		self.assertEqual(self.status_of(batch), "Quarantine")
		self.assertIsNone(frappe.db.get_value("Batch", batch, "fm_released_by"))

	def test_cancel_of_recall_restores_earlier_release(self):
		"""Cancelling a hold on a previously released batch restores Released."""
		fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		batch = fixtures.ensure_batch(self.item, "A13", status="Quarantine")
		first = self.make_release(batch, submit=True)
		hold = self.make_release(batch, decision="Hold", submit=True)
		self.assertEqual(self.status_of(batch), "Hold")

		hold.cancel()
		self.assertEqual(self.status_of(batch), "Released")
		self.assertEqual(frappe.db.get_value("Batch", batch, "fm_last_release"), first.name)

	def test_old_decision_cannot_cancel_after_later_hold(self):
		fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		batch = fixtures.ensure_batch(self.item, "A14", status="Quarantine")
		first = self.make_release(batch, submit=True)
		hold = self.make_release(batch, decision="Hold", submit=True)
		with self.assertRaises(frappe.ValidationError):
			first.cancel()
		self.assertEqual(self.status_of(batch), "Hold")
		self.assertEqual(frappe.db.get_value("Batch", batch, "fm_last_release"), hold.name)

	def test_cancel_chain_restores_the_actual_previous_decision(self):
		fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		batch = fixtures.ensure_batch(self.item, "A15", status="Quarantine")
		first = self.make_release(batch, decision="Hold", submit=True)
		second = self.make_release(batch, submit=True)
		self.assertEqual(second.previous_decision, first.name)
		second.cancel()
		self.assertEqual(self.status_of(batch), "Hold")
		self.assertEqual(frappe.db.get_value("Batch", batch, "fm_last_release"), first.name)
		first.cancel()
		self.assertEqual(self.status_of(batch), "Quarantine")

	# -- the status is not an editable field ----------------------------------

	def test_the_status_cannot_be_written_by_saving_the_batch(self):
		"""``read_only`` is a form instruction, not a permission.

		Marking the field read-only keeps it out of the way on the form, and
		does nothing at all on ``/api/resource``, in Data Import or in a Server
		Script. Without a guard, anyone who may write a Batch could release one
		with no inspection and nothing saying who decided.
		"""
		batch = fixtures.ensure_batch(self.item, "A16", status="Quarantine")

		doc = frappe.get_doc("Batch", batch)
		doc.fm_quality_status = "Released"
		with self.assertRaises(frappe.ValidationError):
			doc.save()

		self.assertEqual(self.status_of(batch), "Quarantine")

	def test_the_client_api_cannot_write_the_status_either(self):
		"""The same attempt through the endpoint a browser would use."""
		batch = fixtures.ensure_batch(self.item, "A17", status="Quarantine")

		with self.assertRaises(frappe.ValidationError):
			frappe.client.set_value("Batch", batch, "fm_quality_status", "Released")

		self.assertEqual(self.status_of(batch), "Quarantine")

	def test_a_batch_cannot_be_created_already_released(self):
		"""Nor can the guard be stepped around by setting it at insert."""
		doc = frappe.get_doc(
			{
				"doctype": "Batch",
				"batch_id": f"{fixtures.PREFIX}-A18",
				"item": self.item,
				"fm_quality_status": "Released",
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_the_audit_fields_are_protected_too(self):
		"""Who released it and when are part of the same record."""
		fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		batch = fixtures.ensure_batch(self.item, "A19", status="Quarantine")
		self.make_release(batch, submit=True)

		doc = frappe.get_doc("Batch", batch)
		doc.fm_released_by = "Administrator"
		doc.fm_last_release = None
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	def test_an_edit_that_leaves_the_quality_fields_alone_still_saves(self):
		"""The guard is about four fields, not about locking the document."""
		batch = fixtures.ensure_batch(self.item, "A20", status="Quarantine")

		doc = frappe.get_doc("Batch", batch)
		doc.description = "Blended from the October chilli intake"
		doc.save()

		self.assertEqual(frappe.db.get_value("Batch", batch, "description"), doc.description)
		self.assertEqual(self.status_of(batch), "Quarantine")

	def test_a_release_still_writes_the_status(self):
		"""The one writer that must keep working."""
		fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		batch = fixtures.ensure_batch(self.item, "A21", status="Quarantine")
		release = self.make_release(batch, submit=True)

		self.assertEqual(self.status_of(batch), "Released")
		self.assertEqual(frappe.db.get_value("Batch", batch, "fm_last_release"), release.name)

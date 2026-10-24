"""Phase 4: the queue's decided statuses, and the batch trail."""

import frappe

from food_manufacturing.api.quality import QUEUE_STATUSES, get_batch_trail, get_release_queue
from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.tests import fixtures


class TestBatchTrail(FMTestCase):
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
		self.chilli = fixtures.ensure_item(f"ATrChilli {self.tag}", nature="Raw Material")

	def tearDown(self):
		frappe.set_user("Administrator")
		fixtures.cleanup()
		fixtures.cleanup_users()
		frappe.db.set_single_value(
			"Stock Settings", "enable_serial_and_batch_no_for_item", self.original
		)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

	def receive(self, batch_no, qty=50):
		doc = frappe.get_doc({
			"doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
			"purpose": "Material Receipt", "company": self.site["company"],
			"items": [{
				"item_code": self.chilli, "qty": qty, "t_warehouse": self.site["stores"],
				"basic_rate": 100, "batch_no": batch_no, "use_serial_batch_fields": 1,
			}],
		})
		doc.insert(); doc.submit()
		return doc

	# --- the queue looks back as well as forward ----------------------------

	def test_the_queue_can_be_filtered_to_every_status(self):
		self.assertEqual(QUEUE_STATUSES, ("Quarantine", "Hold", "Released", "Rejected"))

	def test_pending_is_the_default(self):
		held = fixtures.ensure_batch(self.chilli, f"TRH-{self.tag}", status="Hold")
		released = fixtures.ensure_batch(self.chilli, f"TRR-{self.tag}", status="Released")
		self.receive(held)
		self.receive(released)

		names = {row["name"] for row in get_release_queue(self.site["company"])}
		self.assertIn(held, names)
		self.assertNotIn(released, names)

	def test_a_decided_status_can_be_asked_for(self):
		"""A decision log you cannot look back through is not a log."""
		released = fixtures.ensure_batch(self.chilli, f"TRR-{self.tag}", status="Released")
		self.receive(released)

		names = {row["name"] for row in get_release_queue(self.site["company"], status="Released")}
		self.assertIn(released, names)

	def test_rejected_batches_can_be_reviewed(self):
		rejected = fixtures.ensure_batch(self.chilli, f"TRX-{self.tag}", status="Rejected")
		self.receive(rejected)

		names = {row["name"] for row in get_release_queue(self.site["company"], status="Rejected")}
		self.assertIn(rejected, names)

	# --- the trail ----------------------------------------------------------

	def test_a_purchased_lot_has_no_producing_run(self):
		batch = fixtures.ensure_batch(self.chilli, f"TRP-{self.tag}", status="Released")
		self.receive(batch)

		trail = get_batch_trail(batch, self.site["company"])
		self.assertEqual(trail["produced_by"], [])
		self.assertEqual(trail["delivered"], [])

	def test_the_trail_has_the_three_sections(self):
		batch = fixtures.ensure_batch(self.chilli, f"TRS-{self.tag}", status="Released")
		self.receive(batch)

		trail = get_batch_trail(batch, self.site["company"])
		for key in ("consumed", "produced_by", "delivered"):
			self.assertIn(key, trail)
			self.assertIsInstance(trail[key], list)

	def test_an_unknown_batch_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			get_batch_trail(f"{fixtures.PREFIX}-no-such-batch", self.site["company"])

	def test_a_user_without_batch_access_is_refused(self):
		batch = fixtures.ensure_batch(self.chilli, f"TRN-{self.tag}", status="Released")
		self.receive(batch)

		user = fixtures.ensure_user("trailnobody", ())
		frappe.set_user(user)

		with self.assertRaises(frappe.PermissionError):
			get_batch_trail(batch, self.site["company"])

"""Consumption and dispatch must be blocked for ineligible batches.

The API-path tests matter as much as the form ones: the rule is enforced in
doc_events, so these use frappe.client.insert / submit - the same entry point
/api/method uses - to prove the rule is not merely a form script.
"""

import frappe

from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.tests import fixtures


class TestBatchEligibility(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()

	def setUp(self):
		fixtures.cleanup()
		self.policy = fixtures.ensure_policy(self.site)
		self.item = fixtures.ensure_item("Turmeric", nature="Raw Material")

	def tearDown(self):
		fixtures.cleanup()

	def make_issue(self, batch, source=None, target=None, purpose="Material Issue"):
		"""A Stock Entry consuming one batch. Not submitted - validate() is enough."""
		doc = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": purpose,
				"purpose": purpose,
				"company": self.site["company"],
				"items": [
					{
						"item_code": self.item,
						"qty": 1,
						"s_warehouse": source or self.site["stores"],
						"t_warehouse": target,
						"batch_no": batch,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		doc.run_method("validate")
		return doc

	# -- blocked statuses -----------------------------------------------------

	def test_quarantine_batch_cannot_be_consumed(self):
		batch = fixtures.ensure_batch(self.item, "B1", status="Quarantine")
		with self.assertRaises(frappe.ValidationError):
			self.make_issue(batch)

	def test_held_batch_cannot_be_consumed(self):
		batch = fixtures.ensure_batch(self.item, "B2", status="Hold")
		with self.assertRaises(frappe.ValidationError):
			self.make_issue(batch)

	def test_rejected_batch_cannot_be_consumed(self):
		batch = fixtures.ensure_batch(self.item, "B3", status="Rejected")
		with self.assertRaises(frappe.ValidationError):
			self.make_issue(batch)

	def test_released_batch_can_be_consumed(self):
		batch = fixtures.ensure_batch(self.item, "B4", status="Released")
		self.make_issue(batch)  # must not raise

	# -- scope limits: the app must not freeze unrelated stock ---------------

	def test_unmanaged_batch_is_never_blocked(self):
		"""A batch predating this app has no status and must still move."""
		batch = fixtures.ensure_batch(self.item, "B5", status=None)
		self.make_issue(batch)

	def test_no_enforcement_without_a_policy(self):
		frappe.db.delete("FM Manufacturing Policy", {"company": self.site["company"]})
		batch = fixtures.ensure_batch(self.item, "B6", status="Quarantine")
		self.make_issue(batch)

	def test_no_enforcement_when_policy_disabled(self):
		fixtures.ensure_policy(self.site, enabled=0)
		batch = fixtures.ensure_batch(self.item, "B7", status="Quarantine")
		self.make_issue(batch)

	def test_policy_toggle_relaxes_unreleased_rule(self):
		fixtures.ensure_policy(self.site, block_unreleased_consumption=0)
		batch = fixtures.ensure_batch(self.item, "B8", status="Quarantine")
		self.make_issue(batch)

	def test_policy_toggle_relaxes_rejected_rule(self):
		fixtures.ensure_policy(self.site, block_rejected_consumption=0)
		batch = fixtures.ensure_batch(self.item, "B9", status="Rejected")
		self.make_issue(batch)

	# -- permitted quarantine movements --------------------------------------

	def test_quarantine_to_rejected_is_permitted(self):
		"""The disposition move must not be blocked by the rule it serves."""
		batch = fixtures.ensure_batch(self.item, "B10", status="Quarantine")
		self.make_issue(
			batch,
			source=self.site["quarantine"],
			target=self.site["rejected"],
			purpose="Material Transfer",
		)

	def test_quarantine_to_quarantine_is_permitted(self):
		batch = fixtures.ensure_batch(self.item, "B11", status="Quarantine")
		self.make_issue(
			batch,
			source=self.site["quarantine"],
			target=self.site["quarantine"],
			purpose="Material Transfer",
		)

	def test_quarantine_to_stores_is_blocked(self):
		"""Releasing by moving stock, without a release decision, must fail."""
		batch = fixtures.ensure_batch(self.item, "B12", status="Quarantine")
		with self.assertRaises(frappe.ValidationError):
			self.make_issue(
				batch,
				source=self.site["quarantine"],
				target=self.site["stores"],
				purpose="Material Transfer",
			)

	# -- inward movement is never blocked ------------------------------------

	def test_receipt_into_quarantine_is_not_blocked(self):
		"""A row with no source warehouse is inward and out of scope."""
		batch = fixtures.ensure_batch(self.item, "B13", status="Quarantine")
		doc = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"purpose": "Material Receipt",
				"company": self.site["company"],
				"items": [
					{
						"item_code": self.item,
						"qty": 1,
						"t_warehouse": self.site["quarantine"],
						"batch_no": batch,
						"use_serial_batch_fields": 1,
						"basic_rate": 10,
					}
				],
			}
		)
		doc.run_method("validate")

	# -- dispatch -------------------------------------------------------------

	def make_delivery(self, batch, warehouse=None):
		customer = frappe.db.get_value("Customer", {}, "name")
		if not customer:
			self.skipTest("Site has no Customer")

		# new_doc, not get_doc: only new_doc applies the DocType defaults, and a
		# document validated without ever being inserted still needs them -
		# ERPNext reads `is_return` while setting the incoming rate, and None
		# there is not the same as 0.
		doc = frappe.new_doc("Delivery Note")
		doc.company = self.site["company"]
		doc.customer = customer
		doc.append(
			"items",
			{
				"item_code": self.item,
				"qty": 1,
				"rate": 100,
				"warehouse": warehouse or self.site["stores"],
				"batch_no": batch,
				"use_serial_batch_fields": 1,
			},
		)
		doc.run_method("validate")
		return doc

	def test_quarantine_batch_cannot_be_dispatched(self):
		batch = fixtures.ensure_batch(self.item, "B14", status="Quarantine")
		with self.assertRaises(frappe.ValidationError):
			self.make_delivery(batch)

	def test_rejected_batch_cannot_be_dispatched(self):
		batch = fixtures.ensure_batch(self.item, "B15", status="Rejected")
		with self.assertRaises(frappe.ValidationError):
			self.make_delivery(batch)

	def test_quarantine_exception_does_not_apply_to_dispatch(self):
		"""Dispatching *from* quarantine is never a permitted movement."""
		batch = fixtures.ensure_batch(self.item, "B16", status="Quarantine")
		with self.assertRaises(frappe.ValidationError):
			self.make_delivery(batch, warehouse=self.site["quarantine"])

	# -- API path -------------------------------------------------------------

	def test_rule_holds_on_the_api_path(self):
		"""frappe.client.insert is the entry point /api/resource uses."""
		from frappe.client import insert

		batch = fixtures.ensure_batch(self.item, "B17", status="Quarantine")
		payload = {
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Issue",
			"purpose": "Material Issue",
			"company": self.site["company"],
			"items": [
				{
					"item_code": self.item,
					"qty": 1,
					"s_warehouse": self.site["stores"],
					"batch_no": batch,
					"use_serial_batch_fields": 1,
				}
			],
		}

		with self.assertRaises(frappe.ValidationError):
			insert(payload)

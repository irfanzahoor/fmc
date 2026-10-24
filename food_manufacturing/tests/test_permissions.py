"""Authorisation: who may decide, and company isolation.

Permissions are asserted with ``frappe.set_user`` so the real permission engine
runs, rather than by inspecting the DocType JSON.
"""

import frappe

from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.tests import fixtures


class TestPermissions(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()

	def setUp(self):
		fixtures.cleanup()
		fixtures.cleanup_users()
		fixtures.ensure_policy(self.site, require_incoming_inspection=0)
		self.item = fixtures.ensure_item("Cumin", nature="Raw Material")

	def tearDown(self):
		frappe.set_user("Administrator")
		fixtures.cleanup()
		fixtures.cleanup_users()

	def release_payload(self, batch, company=None):
		return {
			"doctype": "FM Batch Release",
			"batch": batch,
			"company": company or self.site["company"],
			"decision": "Release",
		}

	# -- 2.6 only the quality manager may decide -----------------------------

	def test_quality_inspector_cannot_create_a_release(self):
		batch = fixtures.ensure_batch(self.item, "C1", status="Quarantine")
		user = fixtures.ensure_user("inspector", ("FM Quality Inspector",))

		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(self.release_payload(batch)).insert()

	def test_production_operator_cannot_create_a_release(self):
		batch = fixtures.ensure_batch(self.item, "C2", status="Quarantine")
		user = fixtures.ensure_user("operator", ("FM Production Operator",))

		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(self.release_payload(batch)).insert()

	def test_quality_manager_may_release(self):
		batch = fixtures.ensure_batch(self.item, "C3", status="Quarantine")
		user = fixtures.ensure_user("qm", ("FM Quality Manager",))

		frappe.set_user(user)
		doc = frappe.get_doc(self.release_payload(batch))
		doc.insert()
		doc.submit()

		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Batch", batch, "fm_quality_status"), "Released")
		self.assertEqual(frappe.db.get_value("Batch", batch, "fm_released_by"), user)

	def test_quality_inspector_may_still_read(self):
		batch = fixtures.ensure_batch(self.item, "C4", status="Quarantine")
		doc = frappe.get_doc(self.release_payload(batch))
		doc.insert()

		user = fixtures.ensure_user("inspector2", ("FM Quality Inspector",))
		frappe.set_user(user)
		self.assertTrue(frappe.has_permission("FM Batch Release", "read", doc=doc.name))
		self.assertFalse(frappe.has_permission("FM Batch Release", "create"))

	# -- 2.11 cross-company isolation ----------------------------------------

	def test_user_restricted_to_another_company_cannot_read_the_release(self):
		batch = fixtures.ensure_batch(self.item, "C5", status="Quarantine")
		doc = frappe.get_doc(self.release_payload(batch))
		doc.insert()

		user = fixtures.ensure_user("foreign", ("FM Quality Manager",))
		fixtures.restrict_user_to_company(user, self.site["foreign_company"])

		frappe.set_user(user)
		self.assertFalse(frappe.has_permission("FM Batch Release", "read", doc=doc.name))

		# and it must not appear in a permission-respecting list
		names = frappe.get_list(
			"FM Batch Release",
			filters={"name": doc.name},
			fields=["name"],
			ignore_permissions=False,
		)
		self.assertEqual(names, [])

	def test_user_restricted_to_own_company_can_read_the_release(self):
		batch = fixtures.ensure_batch(self.item, "C6", status="Quarantine")
		doc = frappe.get_doc(self.release_payload(batch))
		doc.insert()

		user = fixtures.ensure_user("local", ("FM Quality Manager",))
		fixtures.restrict_user_to_company(user, self.site["company"])

		frappe.set_user(user)
		self.assertTrue(frappe.has_permission("FM Batch Release", "read", doc=doc.name))

	def test_release_for_a_company_the_user_cannot_access_is_blocked(self):
		batch = fixtures.ensure_batch(self.item, "C7", status="Quarantine")
		user = fixtures.ensure_user("foreign2", ("FM Quality Manager",))
		fixtures.restrict_user_to_company(user, self.site["foreign_company"])

		frappe.set_user(user)
		with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
			frappe.get_doc(self.release_payload(batch)).insert()

	# -- policy is read-only to operators ------------------------------------

	def test_operator_cannot_edit_the_policy(self):
		user = fixtures.ensure_user("operator2", ("FM Production Operator",))
		frappe.set_user(user)
		self.assertTrue(frappe.has_permission("FM Manufacturing Policy", "read"))
		self.assertFalse(frappe.has_permission("FM Manufacturing Policy", "write"))

	def test_batch_quality_status_is_read_only_on_the_form(self):
		"""Keeps the field out of the way on the form - and nothing more.

		``read_only`` is an instruction to the form. It is not a permission, and
		this assertion on its own used to read as though it were: the guard that
		actually stops the field being written lives in
		``overrides/batch.py`` and is proved in test_batch_release.py.
		"""
		self.assertEqual(frappe.get_meta("Batch").get_field("fm_quality_status").read_only, 1)

	def test_an_operator_cannot_write_the_quality_status_through_the_api(self):
		"""The boundary itself, from the account that would try it.

		An Item Manager may write a Batch - that is what makes Batch readable to
		the console at all - so without a server-side guard this account could
		release a batch with no inspection and no record of who decided.
		"""
		batch = fixtures.ensure_batch(self.item, "C8", status="Quarantine")
		user = fixtures.ensure_user("itemmgr", ("FM Production Operator", "Item Manager"))

		frappe.set_user(user)
		try:
			with self.assertRaises(frappe.ValidationError):
				frappe.client.set_value("Batch", batch, "fm_quality_status", "Released")
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Batch", batch, "fm_quality_status"), "Quarantine")

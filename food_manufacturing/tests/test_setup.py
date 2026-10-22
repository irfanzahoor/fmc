"""Roles must exist after install and creation must be idempotent."""

import frappe

from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.setup.roles import FM_ROLES, ensure_roles


class TestSetup(FMTestCase):
	def test_all_roles_exist_after_install(self):
		existing = set(
			frappe.get_all("Role", filters={"name": ("in", list(FM_ROLES))}, pluck="name")
		)
		self.assertEqual(existing, set(FM_ROLES))

	def test_ensure_roles_is_idempotent(self):
		before = frappe.db.count("Role")
		ensure_roles()
		ensure_roles()
		self.assertEqual(frappe.db.count("Role"), before)

	def test_roles_have_desk_access(self):
		rows = frappe.get_all(
			"Role",
			filters={"name": ("in", list(FM_ROLES))},
			fields=["name", "desk_access"],
		)
		for row in rows:
			self.assertEqual(row.desk_access, 1, msg=row.name)

	def test_module_def_registered(self):
		self.assertTrue(frappe.db.exists("Module Def", "Food Manufacturing Setup"))

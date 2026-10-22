"""Access control on the operator SPA's HTML shell at /fm.

The shell carries no data, but it should not be served to anonymous visitors or
to portal accounts, so the access rule is asserted rather than assumed.
"""

import frappe

from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.tests import fixtures
from food_manufacturing.www.fm import get_context


class TestOperatorPortal(FMTestCase):
	def setUp(self):
		fixtures.cleanup_users()

	def tearDown(self):
		frappe.set_user("Administrator")
		fixtures.cleanup_users()
		frappe.local.flags.redirect_location = None

	def test_guest_is_redirected_to_login(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.Redirect):
			get_context(frappe._dict())

		self.assertEqual(frappe.local.flags.redirect_location, "/login?redirect-to=/fm")

	def test_staff_user_gets_the_page(self):
		user = fixtures.ensure_user("operator", ("FM Production Operator",))
		frappe.set_user(user)

		context = get_context(frappe._dict())
		self.assertEqual(context.no_cache, 1)

	def test_website_user_is_refused(self):
		"""A portal account is not a shop-floor account."""
		user = fixtures.ensure_user("portal", (), user_type="Website User")
		frappe.set_user(user)

		with self.assertRaises(frappe.PermissionError):
			get_context(frappe._dict())

	def test_route_rule_is_registered(self):
		rules = frappe.get_hooks("website_route_rules")
		routes = {rule["from_route"]: rule["to_route"] for rule in rules}
		self.assertEqual(routes.get("/fm/<path:app_path>"), "fm")

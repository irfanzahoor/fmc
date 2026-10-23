"""The console's first request.

The SPA used to open by asking ``frappe.client.get_list`` for Company. Company
is readable by Stock User, Sales User and the like but by no FM role, so an
operator holding only FM roles got ``Insufficient Permission for Company``
before the first screen rendered. These tests pin both halves of that: the
premise (Company really is unreadable to such a user) and the fix.
"""

import frappe

from food_manufacturing.api.session import _default_company, get_bootstrap
from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.tests import fixtures


class TestSessionBootstrap(FMTestCase):
	def setUp(self):
		self.site = fixtures.require_site()
		fixtures.cleanup_users()
		fixtures.ensure_policy(self.site)

	def tearDown(self):
		frappe.set_user("Administrator")
		fixtures.cleanup_users()

	def test_company_is_unreadable_to_an_fm_only_user(self):
		"""The premise. If this ever fails, the endpoint can be simplified."""
		user = fixtures.ensure_user("boot_operator", ("FM Production Operator",))
		frappe.set_user(user)

		with self.assertRaises(frappe.PermissionError):
			frappe.get_list("Company", pluck="name")

	def test_fm_only_user_still_gets_a_usable_company_list(self):
		user = fixtures.ensure_user("boot_operator", ("FM Production Operator",))
		frappe.set_user(user)

		data = get_bootstrap()

		self.assertIn(self.site["company"], data["configured"])
		self.assertIn(self.site["company"], data["companies"])
		self.assertIn(data["default"], data["companies"])
		self.assertEqual(data["user"], user)

	def test_no_permission_popup_is_left_behind(self):
		"""The swallowed Company error must not reach the browser.

		``frappe.throw`` queues its message before raising, so catching the
		exception alone still shipped a red "Insufficient Permission for
		Company" popup on a request that succeeded.
		"""
		user = fixtures.ensure_user("boot_operator", ("FM Production Operator",))
		frappe.set_user(user)
		frappe.local.message_log = []

		get_bootstrap()

		self.assertEqual(frappe.local.message_log, [])

	def test_a_disabled_policy_is_not_offered_as_configured(self):
		frappe.db.set_value("FM Manufacturing Policy", self.site["company"], "enabled", 0)

		user = fixtures.ensure_user("boot_operator", ("FM Production Manager",))
		frappe.set_user(user)

		self.assertNotIn(self.site["company"], get_bootstrap()["configured"])

	def test_user_permission_narrows_the_list(self):
		"""A user restricted to one company must not learn the others' names."""
		user = fixtures.ensure_user("boot_manager", ("FM Production Manager", "Stock User"))
		fixtures.restrict_user_to_company(user, self.site["company"])
		frappe.set_user(user)

		data = get_bootstrap()

		self.assertEqual(data["companies"], [self.site["company"]])
		self.assertEqual(data["default"], self.site["company"])

	def test_configured_company_beats_the_user_default(self):
		"""Opening on a company with no policy shows an empty app."""
		fallback = self._user_default()
		configured = f"{fixtures.PREFIX} Spice Co"

		self.assertEqual(_default_company([fallback, configured], [configured]), configured)

	def test_user_default_wins_among_configured_companies(self):
		"""Once every candidate has a policy, the user's own default decides.

		The other candidate is passed first, so falling through to "take the
		first configured company" would return it instead.
		"""
		fallback = self._user_default()
		other = f"{fixtures.PREFIX} Spice Co"

		self.assertEqual(_default_company([other, fallback], [other, fallback]), fallback)

	def _user_default(self) -> str:
		"""The site's real company default, rather than a planted one.

		``get_user_default("Company")`` resolves through User Permissions and
		the scrubbed ``company`` key, so writing the default in a test asserts
		the plumbing instead of this module.
		"""
		default = frappe.defaults.get_user_default("Company")
		if not default:
			self.skipTest("Site has no default company")

		return default

	def test_no_companies_at_all_is_not_an_error(self):
		self.assertIsNone(_default_company([], []))

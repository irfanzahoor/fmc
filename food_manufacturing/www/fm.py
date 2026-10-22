"""Server context for the operator SPA at /fm.

The HTML shell carries no data - every figure it shows is fetched from a
whitelisted endpoint that re-checks permission. Even so, an anonymous visitor is
sent to the login page rather than shown an empty application, and a Website
User (a portal account, not a staff account) is refused: the operator screens
are for staff.
"""

import frappe
from frappe import _

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/fm"
		raise frappe.Redirect

	if frappe.db.get_value("User", frappe.session.user, "user_type") != "System User":
		frappe.throw(
			_("The Food Manufacturing console is available to staff accounts only."),
			frappe.PermissionError,
		)

	context.no_cache = 1
	return context

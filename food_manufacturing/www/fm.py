"""Server context for the operator SPA at /fm.

Two jobs:

1. **Access.** The HTML shell carries no business data - every figure comes
   from a whitelisted endpoint that re-checks permission - but an anonymous
   visitor is still sent to the login page rather than shown an empty
   application, and a Website User (a portal account, not a staff account) is
   refused outright.

2. **Boot data.** The built template writes each key of ``boot`` onto
   ``window``. Without it ``window.csrf_token`` is never set, frappe-ui posts
   every request without an ``X-Frappe-CSRF-Token`` header, and Frappe rejects
   the lot with ``CSRFTokenError`` - which looks exactly like an app that
   loads but shows no data.
"""

import frappe
from frappe import _
from frappe.utils import cint

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

	context.boot = get_boot()
	context.no_cache = 1
	return context


def _csrf_token() -> str:
	"""The session's CSRF token, or an empty string.

	Generating one needs a real HTTP session. If that is unavailable the page
	still renders: the app then surfaces its own request errors, which is far
	easier to diagnose than a blank Frappe error page.
	"""
	try:
		return frappe.sessions.get_csrf_token()
	except Exception:
		frappe.log_error(title="FM console: could not issue a CSRF token", message=frappe.get_traceback())
		return ""


def get_boot() -> frappe._dict:
	"""Values the SPA needs before its first request.

	``get_csrf_token`` persists a freshly generated token to the session
	itself, so no explicit commit is needed here.
	"""
	user = frappe.session.user

	return frappe._dict(
		{
			"csrf_token": _csrf_token(),
			"sysdefaults": frappe.defaults.get_defaults(),
			"fm_boot": {
				"user": user,
				"full_name": frappe.db.get_value("User", user, "full_name"),
				"roles": frappe.get_roles(user),
				"site_name": frappe.local.site,
				"frappe_version": frappe.__version__,
				"developer_mode": cint(frappe.conf.get("developer_mode")),
			},
		}
	)

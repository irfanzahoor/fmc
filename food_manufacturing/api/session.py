"""What the console needs before its first screen.

The app used to ask ``frappe.client.get_list`` for Company directly. Company is
readable by Stock User, Sales User, Accounts User and the like - but **not** by
any FM role, so an operator holding only FM roles could not get past the first
request. The whole point of those roles is that such an operator can run the
plant, so the company list is derived from the FM Manufacturing Policy instead,
which every FM role can read, and Company is only a fallback.

One call also replaces two round trips on page load.
"""

import frappe


@frappe.whitelist()
def get_bootstrap() -> dict:
	"""Companies this user may work in, and which one to open on."""
	configured = _configured_companies()
	companies = _visible_companies(configured)
	default = _default_company(companies, configured)

	return {
		"companies": companies,
		"configured": configured,
		"default": default,
		"user": frappe.session.user,
	}


def _readable_names(doctype: str, filters: dict | None = None) -> list | None:
	"""Names of the records this user may read, or None if the DocType is shut.

	``frappe.throw`` queues its message *before* raising, so catching the
	PermissionError is not enough on its own: the queued
	"Insufficient Permission for Company" would still reach the browser as a
	red popup on a request that in fact succeeded. The log is trimmed back to
	where it started for that reason.
	"""
	marker = len(frappe.local.message_log)
	try:
		return frappe.get_list(
			doctype,
			filters=filters or {},
			pluck="name",
			order_by="name asc",
			limit_page_length=0,
		)
	except frappe.PermissionError:
		del frappe.local.message_log[marker:]
		return None


def _configured_companies() -> list:
	"""Companies with an enabled policy, as far as this user can see.

	The policy is named after its company, so the names are the companies.
	``get_list`` applies the user's permissions and User Permissions, so a user
	restricted to one company sees only that one.
	"""
	return _readable_names("FM Manufacturing Policy", {"enabled": 1}) or []


def _visible_companies(configured: list) -> list:
	"""Every company this user can see, or just the configured ones.

	A user with FM roles alone cannot read Company. Falling back to the
	configured list keeps the switcher working for exactly that operator
	instead of failing the whole page.
	"""
	companies = _readable_names("Company")
	if companies is None:
		return list(configured)

	# A configured company the user can reach should never drop out of the
	# switcher because Company itself is filtered more tightly.
	missing = [name for name in configured if name not in companies]
	return sorted(companies + missing)


def _default_company(companies: list, configured: list) -> str | None:
	"""Prefer a company that has something to show.

	Opening on a company with no policy shows an empty dashboard, which reads
	as a broken app, so a configured company beats the user's default and the
	merely-alphabetical first.
	"""
	user_default = frappe.defaults.get_user_default("Company")

	if user_default and user_default in configured:
		return user_default
	if configured:
		return configured[0]
	if user_default and user_default in companies:
		return user_default

	return companies[0] if companies else None

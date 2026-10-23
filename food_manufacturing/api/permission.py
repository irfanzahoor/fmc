"""Who sees Batchwell on the apps screen."""

import frappe


def has_app_permission() -> bool:
	"""Whether this user has any business inside the app.

	Gating on System Manager would be wrong: the people who live in it are
	plant, quality and warehouse staff. Read access on the company policy is
	the honest test - it is the record the app cannot work without, and every
	FM role the app ships can read it, while nobody else can.
	"""
	if frappe.session.user == "Administrator":
		return True

	return bool(frappe.has_permission("FM Manufacturing Policy", "read"))

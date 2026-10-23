"""Retire the old 'Food Manufacturing' workspace.

The workspace was renamed to the product brand. Its record name is its primary
key, so the sync creates the new one and leaves the old behind - two entries in
the sidebar, one of them stale. This removes the old one.

Idempotent: a site that never had it, or has already run this, does nothing.
"""

import frappe

OLD = "Food Manufacturing"
NEW = "Batchwell"


def execute():
	if not frappe.db.exists("Workspace", OLD):
		return

	# Only remove the old entry once the new one is actually in place, so a
	# half-finished migrate never leaves the app with no sidebar entry at all.
	if not frappe.db.exists("Workspace", NEW):
		return

	frappe.delete_doc("Workspace", OLD, force=True, ignore_permissions=True)

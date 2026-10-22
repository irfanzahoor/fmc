"""Stock approaching, or past, its expiry date.

Shares its query with the daily alert in tasks/near_expiry.py, so the screen and
the email can never disagree about what is expiring.
"""

import frappe
from frappe import _
from frappe.utils import cint

from food_manufacturing.tasks.near_expiry import get_near_expiry_batches

DEFAULT_HORIZON_DAYS = 30


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Batch"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 160},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 170},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 170},
		{"label": _("Qty On Hand"), "fieldname": "qty", "fieldtype": "Float", "width": 110},
		{"label": _("Expiry"), "fieldname": "expiry_date", "fieldtype": "Date", "width": 100},
		{"label": _("Days to Expiry"), "fieldname": "days_to_expiry", "fieldtype": "Int", "width": 120},
		{"label": _("Quality Status"), "fieldname": "quality_status", "fieldtype": "Data", "width": 120},
	]


def get_data(filters):
	company = filters.get("company") or frappe.defaults.get_user_default("Company")
	if not company:
		frappe.throw(_("Select a company."))

	within_days = cint(filters.get("within_days")) or _policy_horizon(company)

	return get_near_expiry_batches(company, within_days)


def _policy_horizon(company: str) -> int:
	"""Default the horizon to the company's own alert setting."""
	configured = frappe.db.get_value(
		"FM Manufacturing Policy", company, "near_expiry_alert_days"
	)
	return cint(configured) or DEFAULT_HORIZON_DAYS

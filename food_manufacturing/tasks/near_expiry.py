"""Daily near-expiry alerting.

Driven by ``FM Manufacturing Policy.near_expiry_alert_days`` per company, so one
plant can watch 30 days ahead while another watches 90. A value of 0 disables
alerts for that company.

Only batches that still have stock are reported - an expiring batch with nothing
left in it is not a problem anybody needs waking up for.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, today

from food_manufacturing.stock_levels import get_batch_quantities

#: Roles notified about expiring stock.
NOTIFY_ROLES = ("FM Quality Manager", "FM Production Manager", "FM Warehouse Operator")


def send_near_expiry_alerts() -> None:
	"""Scheduled daily. One notification per company with expiring stock."""
	policies = frappe.get_all(
		"FM Manufacturing Policy",
		filters={"enabled": 1, "near_expiry_alert_days": (">", 0)},
		fields=["name", "company", "near_expiry_alert_days"],
		order_by="name asc",
	)

	for policy in policies:
		try:
			batches = get_near_expiry_batches(policy.company, policy.near_expiry_alert_days)
			if batches:
				_notify(policy.company, batches)
		except Exception:
			# A failure for one company must not stop the others.
			frappe.log_error(
				title=f"Near-expiry alert failed for {policy.company}",
				message=frappe.get_traceback(),
			)


def get_near_expiry_batches(company: str, within_days: int) -> list:
	"""Batches with stock that expire within ``within_days``.

	Expired batches are included: they are the most urgent case, and leaving
	them out would hide stock that must be quarantined or written off.
	"""
	horizon = add_days(getdate(today()), cint(within_days))

	batches = frappe.get_all(
		"Batch",
		filters={
			"disabled": 0,
			"expiry_date": ("<=", horizon),
			"fm_quality_status": ("not in", ("Rejected",)),
		},
		fields=["name", "item", "item_name", "expiry_date", "fm_quality_status"],
		order_by="expiry_date asc, name asc",
	)
	if not batches:
		return []

	quantities = _batch_quantities([batch.name for batch in batches], company)

	near_expiry = []
	for batch in batches:
		qty = flt(quantities.get(batch.name))
		if qty <= 0:
			continue

		near_expiry.append(
			{
				"batch_no": batch.name,
				"item_code": batch.item,
				"item_name": batch.item_name,
				"expiry_date": batch.expiry_date,
				"quality_status": batch.fm_quality_status,
				"qty": qty,
				"days_to_expiry": (getdate(batch.expiry_date) - getdate(today())).days,
			}
		)

	return near_expiry


def _batch_quantities(batch_names: list, company: str) -> dict:
	"""On-hand quantity per batch, scoped to one company's warehouses."""
	warehouses = frappe.get_all(
		"Warehouse", filters={"company": company}, pluck="name", order_by="name asc"
	)
	if not warehouses:
		return {}

	return get_batch_quantities(batch_names, warehouses)


def _notify(company: str, batches: list) -> None:
	"""Raise one Notification Log per recipient for this company."""
	recipients = _recipients()
	if not recipients:
		return

	expired = [b for b in batches if b["days_to_expiry"] < 0]
	subject = _("{0}: {1} batches near expiry, {2} already expired").format(
		company, len(batches), len(expired)
	)

	lines = [
		_("{0} ({1}) - {2} expires {3}").format(
			batch["batch_no"],
			batch["item_code"],
			flt(batch["qty"]),
			frappe.format_value(batch["expiry_date"], {"fieldtype": "Date"}),
		)
		for batch in batches[:50]
	]
	if len(batches) > 50:
		lines.append(_("...and {0} more.").format(len(batches) - 50))

	for user in recipients:
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": user,
				"type": "Alert",
				"subject": subject,
				"email_content": "<br>".join(lines),
			}
		).insert(ignore_permissions=True)  # system-generated alert, no session user


def _recipients() -> list:
	"""Enabled users holding any notified role."""
	users = frappe.get_all(
		"Has Role",
		filters={"role": ("in", NOTIFY_ROLES), "parenttype": "User"},
		pluck="parent",
		order_by="parent asc",
	)
	if not users:
		return []

	return frappe.get_all(
		"User",
		filters={"name": ("in", list(set(users))), "enabled": 1},
		pluck="name",
		order_by="name asc",
	)

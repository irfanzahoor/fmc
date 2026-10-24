"""Expiry and remaining-shelf-life rules at dispatch.

Customers of a spice plant buy on remaining shelf life, not just on "not yet
expired", so two separate questions are asked of every batch leaving the
building:

1. Has it expired? Governed by ``block_expired_dispatch``.
2. Does enough of its shelf life remain? Governed by
   ``min_remaining_shelf_life_percent``.

Both are enforced through ``doc_events`` on Delivery Note, so they hold on the
form, on ``/api/resource`` and through Data Import - not only where a button
happens to be wired up.

Scope limits, deliberately the same as the quality gate: a batch with no
``expiry_date`` is not shelf-life managed and is never blocked, and nothing is
enforced for a company with no enabled policy. Installing this app must not
freeze stock that is already moving.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today

from food_manufacturing.food_manufacturing_setup.doctype.fm_manufacturing_policy.fm_manufacturing_policy import (
	get_policy_if_any,
)
from food_manufacturing.quality.batch_eligibility import get_row_batches, is_inward


def validate_delivery_note(doc, method=None) -> None:
	"""Block expired or too-near-expiry batches on a Delivery Note."""
	policy = get_policy_if_any(doc.company)
	if not policy:
		return

	# A return is a Delivery Note with negative quantities: the stock is coming
	# back, and stock coming back is not a dispatch. Without this, a customer
	# could not return the near-expiry stock a recall has just asked them for.
	rows = [row for row in doc.get("items") or [] if row.get("warehouse") and not is_inward(row)]
	if not rows:
		return

	batches_by_row = get_row_batches(rows, "Delivery Note Item")
	if not batches_by_row:
		return

	all_batches = {b for batches in batches_by_row.values() for b in batches}
	details = get_batch_shelf_life(all_batches)
	if not details:
		return

	posting_date = getdate(doc.get("posting_date") or today())

	for row in rows:
		for batch_no in sorted(batches_by_row.get(row.name, ())):
			detail = details.get(batch_no)
			if not detail or not detail["expiry_date"]:
				# Not shelf-life managed.
				continue

			_check_expiry(policy, row, batch_no, detail, posting_date)
			_check_remaining_shelf_life(policy, row, batch_no, detail, posting_date)


def _check_expiry(policy, row, batch_no, detail, posting_date) -> None:
	if not cint(policy.block_expired_dispatch):
		return

	if getdate(detail["expiry_date"]) >= posting_date:
		return

	frappe.throw(
		_("Row {0}: batch {1} of item {2} expired on {3} and cannot be dispatched.").format(
			row.idx,
			frappe.bold(batch_no),
			frappe.bold(row.item_code),
			frappe.bold(frappe.format_value(detail["expiry_date"], {"fieldtype": "Date"})),
		),
		title=_("Expired Stock"),
	)


def _check_remaining_shelf_life(policy, row, batch_no, detail, posting_date) -> None:
	minimum = flt(policy.min_remaining_shelf_life_percent)
	if minimum <= 0:
		return

	remaining = remaining_shelf_life_percent(detail, posting_date)
	if remaining is None:
		# Total shelf life is unknown, so a percentage cannot honestly be
		# computed. The expiry check above still applies.
		return

	if remaining >= minimum:
		return

	frappe.throw(
		_(
			"Row {0}: batch {1} of item {2} has {3}% of its shelf life left, "
			"below the {4}% required for dispatch."
		).format(
			row.idx,
			frappe.bold(batch_no),
			frappe.bold(row.item_code),
			frappe.bold(flt(remaining, 2)),
			frappe.bold(flt(minimum, 2)),
		),
		title=_("Insufficient Remaining Shelf Life"),
	)


def remaining_shelf_life_percent(detail: dict, as_of=None):
	"""Percentage of total shelf life still remaining, or None if unknowable.

	Total shelf life is taken from the batch's own manufacturing and expiry
	dates when both are present, and otherwise from the Item's
	``shelf_life_in_days``. With neither, the answer is None rather than a
	guess.
	"""
	expiry = detail.get("expiry_date")
	if not expiry:
		return None

	as_of = getdate(as_of or today())
	expiry = getdate(expiry)

	total_days = None
	manufactured = detail.get("manufacturing_date")
	if manufactured:
		total_days = (expiry - getdate(manufactured)).days
	elif detail.get("shelf_life_in_days"):
		total_days = cint(detail["shelf_life_in_days"])

	if not total_days or total_days <= 0:
		return None

	remaining_days = (expiry - as_of).days
	if remaining_days < 0:
		return 0.0

	return flt(remaining_days / total_days * 100.0, 4)


def get_batch_shelf_life(batch_names) -> dict:
	"""Shelf-life facts for a set of batches, in two queries."""
	if not batch_names:
		return {}

	batches = frappe.get_all(
		"Batch",
		filters={"name": ("in", list(batch_names))},
		fields=["name", "item", "expiry_date", "manufacturing_date"],
		order_by="name asc",
	)
	if not batches:
		return {}

	item_codes = {batch.item for batch in batches if batch.item}
	shelf_life_by_item = {}
	if item_codes:
		shelf_life_by_item = dict(
			frappe.get_all(
				"Item",
				filters={"name": ("in", list(item_codes))},
				fields=["name", "shelf_life_in_days"],
				as_list=True,
				order_by="name asc",
			)
		)

	return {
		batch.name: {
			"item": batch.item,
			"expiry_date": batch.expiry_date,
			"manufacturing_date": batch.manufacturing_date,
			"shelf_life_in_days": shelf_life_by_item.get(batch.item),
		}
		for batch in batches
	}

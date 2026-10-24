"""Batch quality eligibility enforcement.

Wired through ``doc_events`` in hooks.py rather than form buttons, so the rules
hold on every path that reaches the database: the Desk form, ``/api/resource``,
``/api/method``, Data Import, and any server-side script that saves or submits a
Stock Entry or Delivery Note.

Three deliberate limits on scope:

1. A batch whose ``fm_quality_status`` is blank is **not quality-managed** and is
   never blocked. Installing this app must not freeze stock that is already
   moving on a live site, and batches created before the app existed have no
   status.
2. Nothing is enforced for a company with no enabled ``FM Manufacturing
   Policy``. Policy is opt-in per company.
3. Only rows that move stock **out** are checked. A customer return is a
   Delivery Note with negative quantities, which is stock coming back - see
   :func:`is_inward`.
"""

import frappe
from frappe import _
from frappe.utils import flt

from food_manufacturing.food_manufacturing_setup.doctype.fm_manufacturing_policy.fm_manufacturing_policy import (
	get_policy_if_any,
)

#: Statuses that are never consumable or dispatchable when policy blocks them.
BLOCKED_BY_REJECTION = ("Hold", "Rejected")

#: Role permitted to move stock out of the rejected warehouse (supplier return
#: or authorised write-off).
REJECTED_DISPOSAL_ROLE = "FM Quality Manager"


def validate_stock_entry(doc, method=None):
	"""Block consumption of ineligible batches on a Stock Entry."""
	policy = get_policy_if_any(doc.company)
	if not policy:
		return

	rows = [(row, row.s_warehouse, row.t_warehouse) for row in doc.get("items") or [] if not is_inward(row)]
	_validate_rows(policy, rows, "Stock Entry Detail", context="consumption")


def validate_delivery_note(doc, method=None):
	"""Block dispatch of ineligible batches on a Delivery Note."""
	policy = get_policy_if_any(doc.company)
	if not policy:
		return

	rows = [(row, row.warehouse, None) for row in doc.get("items") or [] if not is_inward(row)]
	_validate_rows(policy, rows, "Delivery Note Item", context="dispatch")


def is_inward(row) -> bool:
	"""Whether this row brings stock in rather than sending it out.

	ERPNext writes a customer return as a Delivery Note whose rows carry
	negative quantities, and a supplier return as a Purchase Receipt the same
	way. The stock is arriving, so none of the outward rules apply to it: a
	batch put on Hold after a recall is exactly the batch a customer is sending
	back, and refusing the return would leave the stock recorded as still out
	there - the opposite of what a recall needs.

	The sign is read per row rather than from ``is_return`` on the parent, so a
	document carrying both directions is judged row by row.
	"""
	return flt(row.get("qty")) < 0


# -- internals ---------------------------------------------------------------


def _validate_rows(policy, rows, child_doctype: str, context: str) -> None:
	"""Check every outward row against the batch quality policy."""
	outward = [(row, source, target) for row, source, target in rows if source]
	if not outward:
		return

	batches_by_row = get_row_batches([row for row, _s, _t in outward], child_doctype)
	if not batches_by_row:
		return

	statuses = _get_batch_statuses({b for batches in batches_by_row.values() for b in batches})
	if not statuses:
		return

	for row, source, target in outward:
		for batch_no in batches_by_row.get(row.name, ()):
			status = statuses.get(batch_no)
			# Blank or missing status -> not quality-managed, never blocked.
			if not status:
				continue

			_check_batch(policy, row, batch_no, status, source, target, context)


def _check_batch(policy, row, batch_no, status, source, target, context: str) -> None:
	if status == "Released":
		return

	if _is_permitted_quarantine_movement(policy, status, source, target, context):
		return

	if status in BLOCKED_BY_REJECTION and policy.block_rejected_consumption:
		_throw(row, batch_no, status, context)

	if status == "Quarantine" and policy.block_unreleased_consumption:
		_throw(row, batch_no, status, context)


def _is_permitted_quarantine_movement(policy, status, source, target, context: str) -> bool:
	"""Movements that quality control itself depends on.

	Documented in ``docs/workflows.md``. Dispatch is never one of them.
	"""
	if context != "consumption":
		return False

	# Quarantine -> rejected is the disposition move, and quarantine -> quarantine
	# is a bin-to-bin shuffle. Neither releases anything.
	if source == policy.quarantine_warehouse and target in (
		policy.rejected_warehouse,
		policy.quarantine_warehouse,
	):
		return True

	# Rejected -> anywhere is a supplier return or an authorised write-off, and is
	# restricted to the role that owns rejected stock.
	if source == policy.rejected_warehouse:
		if REJECTED_DISPOSAL_ROLE in frappe.get_roles() or "System Manager" in frappe.get_roles():
			return True

		frappe.throw(
			_("Only {0} may move stock out of the rejected warehouse {1}.").format(
				frappe.bold(_(REJECTED_DISPOSAL_ROLE)), frappe.bold(policy.rejected_warehouse)
			),
			title=_("Not Permitted"),
		)

	return False


def _throw(row, batch_no, status, context: str) -> None:
	message = (
		_("Row {0}: batch {1} of item {2} is {3} and cannot be consumed.")
		if context == "consumption"
		else _("Row {0}: batch {1} of item {2} is {3} and cannot be dispatched.")
	)

	frappe.throw(
		message.format(
			row.idx,
			frappe.bold(batch_no),
			frappe.bold(row.item_code),
			frappe.bold(_(status)),
		),
		title=_("Batch Not Released"),
	)


def get_row_batches(rows, child_doctype: str | None = None) -> dict:
	"""Map row name -> set of batch numbers it moves.

	Batches reach a row two ways in ERPNext v15/v16: directly on ``batch_no``
	when ``use_serial_batch_fields`` is set, or through a Serial and Batch
	Bundle. Both are collected, and bundle entries are fetched in one query
	rather than per row.

	``rows`` may be child documents or plain dicts read back from the database -
	anything supporting ``.get()`` and ``.name``.

	When ``child_doctype`` is given, rows that carry neither a batch nor a bundle
	in memory are looked up in the database. ERPNext assigns
	``serial_and_batch_bundle`` with ``frappe.db.set_value`` during submit, which
	leaves the in-memory child rows stale, so without this backfill an on_submit
	check would see no batches at all.
	"""
	rows = _backfill_rows(rows, child_doctype)

	by_row = {}
	bundle_rows = {}

	for row in rows:
		batches = set()
		if row.get("batch_no"):
			batches.add(row.batch_no)

		bundle = row.get("serial_and_batch_bundle")
		if bundle:
			bundle_rows.setdefault(bundle, []).append(row.name)

		if batches:
			by_row[row.name] = batches

	if bundle_rows:
		entries = frappe.get_all(
			"Serial and Batch Entry",
			filters={"parent": ("in", list(bundle_rows)), "batch_no": ("is", "set")},
			fields=["parent", "batch_no"],
			order_by="parent asc, idx asc",
		)

		for entry in entries:
			for row_name in bundle_rows.get(entry.parent, ()):
				by_row.setdefault(row_name, set()).add(entry.batch_no)

	return by_row


def _backfill_rows(rows, child_doctype: str | None):
	"""Replace rows with no batch information by their database state."""
	if not child_doctype:
		return rows

	stale = [row.name for row in rows if not (row.get("batch_no") or row.get("serial_and_batch_bundle"))]
	if not stale:
		return rows

	fresh = frappe.get_all(
		child_doctype,
		filters={"name": ("in", stale)},
		fields=["name", "item_code", "batch_no", "serial_and_batch_bundle"],
		order_by="name asc",
	)
	fresh_by_name = {row.name: row for row in fresh}
	if not fresh_by_name:
		return rows

	merged = []
	for row in rows:
		replacement = fresh_by_name.get(row.name)
		if replacement and (replacement.batch_no or replacement.serial_and_batch_bundle):
			# Keep idx for the error message; it is not stored on the fetched row.
			replacement.idx = row.get("idx")
			merged.append(replacement)
		else:
			merged.append(row)

	return merged


def _get_batch_statuses(batch_names) -> dict:
	"""Map batch name -> quality status, in one query."""
	if not batch_names:
		return {}

	rows = frappe.get_all(
		"Batch",
		filters={"name": ("in", list(batch_names))},
		fields=["name", "fm_quality_status"],
		order_by="name asc",
	)

	return {row.name: row.fm_quality_status for row in rows}

"""Deterministic First Expiry First Out recommendation and enforcement.

ERPNext can pick batches automatically, but the order depends on
``Stock Settings.pick_serial_and_batch_based_on`` and, for equal dates, on
whatever order the database returns rows in. A recall-grade system cannot have
"which batch did we ship?" depend on that, so the ordering here is fully
specified and total:

1. ``expiry_date`` ascending, with batches that never expire last.
2. ``manufacturing_date`` ascending, with unknown dates last.
3. ``batch_id`` ascending - the explicit tie-break that makes the result total,
   so the same inputs always give the same answer on any database.

Enforcement is governed by ``FM Manufacturing Policy.enforce_fefo``:

* ``Off``   - recommend only, never complain.
* ``Warn``  - message the user, let them proceed. The default, because plants
  have legitimate reasons to break FEFO.
* ``Block`` - refuse the dispatch.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from food_manufacturing.dispatch.shelf_life import get_batch_shelf_life
from food_manufacturing.food_manufacturing_setup.doctype.fm_manufacturing_policy.fm_manufacturing_policy import (
	get_policy_if_any,
)
from food_manufacturing.quality.batch_eligibility import get_row_batches

#: Sorts after any real date, so never-expiring batches go last.
_FAR_FUTURE = getdate("2999-12-31")

#: Only released batches may be recommended; see quality/batch_eligibility.py
#: for the enforcement of that at consumption and dispatch.
DISPATCHABLE_STATUSES = ("", None, "Released")


@frappe.whitelist()
def get_fefo_recommendation(item_code: str, warehouse: str, qty: float = 0, company: str | None = None):
	"""Batches to pick for ``qty``, in FEFO order.

	Whitelisted for the dispatch screen. Read-only, and it reports only
	quantities the caller may already see through the stock reports, but it
	still checks read permission on Batch so it cannot be used as a side
	channel.
	"""
	frappe.has_permission("Batch", "read", throw=True)

	candidates = get_fefo_batches(item_code, warehouse, company)
	wanted = flt(qty)
	if not wanted:
		return candidates

	picked = []
	remaining = wanted
	for batch in candidates:
		if remaining <= 0:
			break

		take = min(flt(batch["available_qty"]), remaining)
		if take <= 0:
			continue

		picked.append({**batch, "suggested_qty": flt(take)})
		remaining -= take

	return {
		"batches": picked,
		"shortfall": flt(remaining) if remaining > 0 else 0.0,
	}


def get_fefo_batches(item_code: str, warehouse: str, company: str | None = None) -> list:
	"""Available batches of an item in a warehouse, in deterministic FEFO order."""
	from erpnext.stock.doctype.batch.batch import get_available_batches

	available = get_available_batches(
		frappe._dict(item_code=item_code, warehouse=warehouse)
	)
	batch_names = [name for name, qty in (available or {}).items() if flt(qty) > 0]
	if not batch_names:
		return []

	details = get_batch_shelf_life(batch_names)
	statuses = _quality_statuses(batch_names)

	rows = []
	for batch_no in batch_names:
		if statuses.get(batch_no) not in DISPATCHABLE_STATUSES:
			continue

		detail = details.get(batch_no) or {}
		rows.append(
			{
				"batch_no": batch_no,
				"available_qty": flt(available[batch_no]),
				"expiry_date": detail.get("expiry_date"),
				"manufacturing_date": detail.get("manufacturing_date"),
				"quality_status": statuses.get(batch_no),
			}
		)

	return sorted(rows, key=_fefo_sort_key)


def _fefo_sort_key(row):
	"""Total ordering: expiry, then manufacturing date, then batch id."""
	return (
		getdate(row["expiry_date"]) if row["expiry_date"] else _FAR_FUTURE,
		getdate(row["manufacturing_date"]) if row["manufacturing_date"] else _FAR_FUTURE,
		row["batch_no"],
	)


def validate_delivery_note(doc, method=None) -> None:
	"""Warn about, or block, a non-FEFO pick depending on the policy."""
	policy = get_policy_if_any(doc.company)
	if not policy:
		return

	mode = policy.enforce_fefo or "Off"
	if mode == "Off":
		return

	rows = [row for row in doc.get("items") or [] if row.get("warehouse")]
	if not rows:
		return

	batches_by_row = get_row_batches(rows, "Delivery Note Item")
	if not batches_by_row:
		return

	breaches = _find_breaches(rows, batches_by_row, doc.company)
	if not breaches:
		return

	message = _("FEFO: {0}").format("<br>".join(breaches))
	if mode == "Block":
		frappe.throw(message, title=_("Not the Earliest Expiring Batch"))

	frappe.msgprint(message, title=_("Not the Earliest Expiring Batch"), indicator="orange")


def _find_breaches(rows, batches_by_row, company) -> list:
	"""One message per row that skipped an earlier-expiring batch."""
	breaches = []

	for row in rows:
		chosen = batches_by_row.get(row.name)
		if not chosen:
			continue

		candidates = get_fefo_batches(row.item_code, row.warehouse, company)
		if not candidates:
			continue

		earliest = candidates[0]
		if earliest["batch_no"] in chosen:
			continue

		# Only a breach if the skipped batch actually expires sooner than
		# everything picked, otherwise a split pick would be reported wrongly.
		chosen_keys = [_fefo_sort_key(c) for c in candidates if c["batch_no"] in chosen]
		if chosen_keys and _fefo_sort_key(earliest) >= min(chosen_keys):
			continue

		breaches.append(
			_("Row {0}: batch {1} expires sooner than the batch picked for {2}.").format(
				row.idx,
				frappe.bold(earliest["batch_no"]),
				frappe.bold(row.item_code),
			)
		)

	return breaches


def _quality_statuses(batch_names) -> dict:
	rows = frappe.get_all(
		"Batch",
		filters={"name": ("in", list(batch_names))},
		fields=["name", "fm_quality_status"],
		order_by="name asc",
	)
	return {row.name: row.fm_quality_status for row in rows}

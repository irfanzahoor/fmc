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

from food_manufacturing.compat.bundle import get_entries
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
	return get_fefo_batches_bulk([(item_code, warehouse)], company).get((item_code, warehouse), [])


def get_fefo_batches_bulk(requests, company=None) -> dict:
	"""Load all requested item/warehouse candidates without queries per line."""
	from food_manufacturing.stock_levels import get_batch_balances, get_reserved_batch_quantities

	requests = set(requests)
	items = {item for item, warehouse in requests if item and warehouse}
	warehouses = {warehouse for item, warehouse in requests if item and warehouse}
	if not items or not warehouses:
		return {}
	if company:
		warehouses = set(
			frappe.get_all(
				"Warehouse",
				filters={"name": ("in", list(warehouses)), "company": company},
				pluck="name",
				order_by="name asc",
			)
		)
	if not warehouses:
		return {}
	batches = frappe.get_all(
		"Batch",
		filters={"item": ("in", list(items)), "disabled": 0},
		fields=["name", "item", "expiry_date", "manufacturing_date", "fm_quality_status"],
		order_by="name asc",
	)
	balances = get_batch_balances([batch.name for batch in batches], warehouses)
	reserved = get_reserved_batch_quantities([batch.name for batch in batches], warehouses)
	result = {key: [] for key in requests}
	today = getdate()
	for batch in batches:
		if batch.fm_quality_status not in DISPATCHABLE_STATUSES:
			continue
		if batch.expiry_date and getdate(batch.expiry_date) < today:
			continue
		for warehouse in warehouses:
			key = (batch.item, warehouse)
			qty = balances.get((batch.name, warehouse), 0) - reserved.get((batch.name, warehouse), 0)
			if key in result and qty > 0:
				result[key].append(
					{
						"batch_no": batch.name,
						"available_qty": qty,
						"expiry_date": batch.expiry_date,
						"manufacturing_date": batch.manufacturing_date,
						"quality_status": batch.fm_quality_status,
					}
				)
	return {key: sorted(rows, key=_fefo_sort_key) for key, rows in result.items()}


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

	breaches = _find_breaches(rows, batches_by_row, doc.company, policy)
	if not breaches:
		return

	message = _("FEFO: {0}").format("<br>".join(breaches))
	if mode == "Block":
		frappe.throw(message, title=_("Not the Earliest Expiring Batch"))

	frappe.msgprint(message, title=_("Not the Earliest Expiring Batch"), indicator="orange")


def _find_breaches(rows, batches_by_row, company, policy=None) -> list:
	"""Compare total picked stock quantities with the eligible FEFO allocation."""
	from food_manufacturing.dispatch.shelf_life import remaining_shelf_life_percent

	available = get_fefo_batches_bulk([(row.item_code, row.warehouse) for row in rows], company)
	details = get_batch_shelf_life([batch["batch_no"] for group in available.values() for batch in group])
	minimum = flt(policy.min_remaining_shelf_life_percent) if policy else 0
	bundle_names = [row.get("serial_and_batch_bundle") for row in rows if row.get("serial_and_batch_bundle")]
	entries = (
		get_entries(
			filters={"parent": ("in", bundle_names), "is_cancelled": 0},
			fields=["parent", "batch_no", "qty"],
			order_by="parent asc, idx asc",
		)
		if bundle_names
		else []
	)
	bundles = {}
	for entry in entries:
		bundles.setdefault(entry.parent, []).append(entry)
	picked = {}
	for row in rows:
		if not batches_by_row.get(row.name) or flt(row.qty) <= 0:
			continue
		group = picked.setdefault((row.item_code, row.warehouse), {})
		if row.get("serial_and_batch_bundle"):
			for entry in bundles.get(row.serial_and_batch_bundle, []):
				group[entry.batch_no] = group.get(entry.batch_no, 0) + abs(flt(entry.qty))
		elif row.get("batch_no"):
			group[row.batch_no] = group.get(row.batch_no, 0) + flt(row.qty) * (
				flt(row.get("conversion_factor")) or 1
			)
	breaches = []
	for key, chosen in picked.items():
		remaining = sum(chosen.values())
		for candidate in available.get(key, []):
			if remaining <= 0:
				break
			life = remaining_shelf_life_percent(details.get(candidate["batch_no"]) or {})
			if life is not None and life < minimum:
				continue
			expected = min(remaining, flt(candidate["available_qty"]))
			if flt(chosen.get(candidate["batch_no"])) + 0.000001 < expected:
				breaches.append(
					_("Batch {0} must be picked before later batches of {1}.").format(
						frappe.bold(candidate["batch_no"]), frappe.bold(key[0])
					)
				)
				break
			remaining -= expected
	return breaches


def _quality_statuses(batch_names) -> dict:
	rows = frappe.get_all(
		"Batch",
		filters={"name": ("in", list(batch_names))},
		fields=["name", "fm_quality_status"],
		order_by="name asc",
	)
	return {row.name: row.fm_quality_status for row in rows}

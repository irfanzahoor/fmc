"""What is actually wrong right now, with a link to each record.

An owner's dashboard is not a scoreboard; it is a list of things that need a
decision. Three kinds of exception are computable from submitted documents
without inventing anything:

* **Material short** - an open run whose remaining requirement exceeds what is
  on hand in its source warehouse.
* **Quality holds** - batches sitting in Quarantine or Hold with stock.
* **Delayed runs** - open runs past the end date they were planned for.

Everything here is read-only and permission-scoped: ``get_list`` applies the
user's own rights, so an exception the reader could not open never appears.
"""

import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import flt, getdate, today

#: Open runs, in the sense that they still have work left.
OPEN_STATUSES = ("Not Started", "In Process")

#: Enough rows to act on; an exception list is not a report.
LIMIT = 50


def get_exceptions(company: str) -> dict:
	"""The three exception lists, each row carrying what it links to."""
	frappe.has_permission("Company", "read", doc=company, throw=True)

	runs = _open_runs(company)

	return {
		"material_short": _material_short(company, runs),
		"quality_holds": _quality_holds(company),
		"delayed_runs": _delayed_runs(runs),
	}


def _open_runs(company: str) -> list:
	"""Submitted Work Orders with work left, if this user may read them."""
	if not frappe.has_permission("Work Order", "read"):
		return []

	return frappe.get_list(
		"Work Order",
		filters={"company": company, "docstatus": 1, "status": ("in", OPEN_STATUSES)},
		fields=[
			"name",
			"production_item",
			"item_name",
			"status",
			"qty",
			"produced_qty",
			"planned_end_date",
			"wip_warehouse",
			"source_warehouse",
		],
		order_by="planned_end_date asc, creation asc",
		limit=LIMIT * 4,
	)


def _material_short(company: str, runs: list) -> list:
	"""Open runs whose remaining requirement is not on hand.

	Required quantity less what has already been transferred is what the run
	still needs; anything beyond the stock in its source warehouse is a
	shortage. Read from Bin, so it is the same number the stock ledger would
	give - this never estimates.
	"""
	if not runs or not frappe.has_permission("Work Order Item", "read"):
		return []

	names = [run.name for run in runs]
	items = frappe.get_all(
		"Work Order Item",
		filters={"parent": ("in", names)},
		fields=[
			"parent",
			"item_code",
			"item_name",
			"required_qty",
			"transferred_qty",
			"consumed_qty",
			"source_warehouse",
			"stock_uom",
		],
	)
	if not items:
		return []

	by_run = {run.name: run for run in runs}
	wanted = {
		(row.item_code, row.source_warehouse or by_run[row.parent].wip_warehouse)
		for row in items
		if row.parent in by_run
	}
	on_hand = _bin_quantities(company, wanted)

	shortages = {}
	for row in items:
		run = by_run.get(row.parent)
		if not run:
			continue

		warehouse = row.source_warehouse or run.wip_warehouse
		outstanding = flt(row.required_qty) - flt(row.transferred_qty) - flt(row.consumed_qty)
		if outstanding <= 0:
			continue

		available = flt(on_hand.get((row.item_code, warehouse)))
		short = outstanding - available
		if short <= 0:
			continue

		entry = shortages.setdefault(
			row.parent,
			{
				"work_order": run.name,
				"item_name": run.item_name or run.production_item,
				"status": run.status,
				"planned_end_date": str(run.planned_end_date) if run.planned_end_date else None,
				"items": [],
			},
		)
		entry["items"].append({
			"item_code": row.item_code,
			"item_name": row.item_name or row.item_code,
			"warehouse": warehouse,
			"required_qty": outstanding,
			"available_qty": available,
			"short_qty": short,
			"uom": row.stock_uom,
		})

	return sorted(shortages.values(), key=lambda row: len(row["items"]), reverse=True)[:LIMIT]


def _bin_quantities(company: str, pairs: set) -> dict:
	"""On-hand quantity per (item, warehouse), in one query."""
	items = {item for item, _warehouse in pairs if item}
	warehouses = {warehouse for _item, warehouse in pairs if warehouse}
	if not items or not warehouses:
		return {}

	# Scoped to the company's own warehouses, so a shortage is never judged
	# against stock that belongs to someone else.
	owned = set(
		frappe.get_all(
			"Warehouse",
			filters={"company": company, "name": ("in", list(warehouses))},
			pluck="name",
		)
	)
	if not owned:
		return {}

	bin_table = frappe.qb.DocType("Bin")
	rows = (
		frappe.qb.from_(bin_table)
		.select(bin_table.item_code, bin_table.warehouse, Sum(bin_table.actual_qty).as_("qty"))
		.where(bin_table.item_code.isin(list(items)))
		.where(bin_table.warehouse.isin(list(owned)))
		.groupby(bin_table.item_code, bin_table.warehouse)
	).run(as_dict=True)

	return {(row.item_code, row.warehouse): flt(row.qty) for row in rows}


def _quality_holds(company: str) -> list:
	"""Batches awaiting a decision, newest problem first.

	Delegates to the quality queue rather than re-querying: that function
	already filters to batches holding stock in this company, and duplicating
	the rule is how the two drift apart.
	"""
	from food_manufacturing.api.quality import get_release_queue

	try:
		return get_release_queue(company, limit=LIMIT)
	except frappe.PermissionError:
		return []


def _delayed_runs(runs: list) -> list:
	"""Open runs past the end date they were planned for."""
	cutoff = getdate(today())

	delayed = [
		{
			"work_order": run.name,
			"item_name": run.item_name or run.production_item,
			"status": run.status,
			"planned_end_date": str(run.planned_end_date),
			"days_late": (cutoff - getdate(run.planned_end_date)).days,
			"pending_qty": flt(run.qty) - flt(run.produced_qty),
		}
		for run in runs
		if run.planned_end_date and getdate(run.planned_end_date) < cutoff
	]

	return sorted(delayed, key=lambda row: row["days_late"], reverse=True)[:LIMIT]

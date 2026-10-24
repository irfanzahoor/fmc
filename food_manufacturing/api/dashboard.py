"""Dashboard aggregates for the operator SPA.

One endpoint per panel would mean five round trips on page load, so the whole
dashboard comes back in one call. Everything is read-only and scoped to one
company, and the figures are the same ones the reports and the Work Order form
show - this module aggregates, it does not recompute.

A note on units: output quantities live in each item's own stock UOM, so a single
"total kg produced" across a mixed catalogue would be arithmetic on incompatible
units. The headline figure is therefore **average actual yield**, a percentage,
which is both unit-free and the number a blending plant actually manages.
"""

import frappe
from frappe.utils import add_days, cint, flt, getdate, today

from food_manufacturing.items import get_item_uoms
from food_manufacturing.stock_levels import get_batch_quantities

#: Expiry buckets, most urgent first - the urgent row leads the chart rather
#: than being buried under a longer bar for a bucket nobody needs to act on.
EXPIRY_BUCKETS = (
	("Expired", None, -1),
	("Within 7 days", 0, 7),
	("8-30 days", 8, 30),
	("31-90 days", 31, 90),
)

QUALITY_STATUSES = ("Released", "Quarantine", "Hold", "Rejected")

#: How many recent runs the yield trend shows.
TREND_RUNS = 12


@frappe.whitelist()
def get_dashboard(company: str, days: int = 30) -> dict:
	"""Every dashboard panel in one read-only call."""
	frappe.has_permission("Work Order", "read", throw=True)
	frappe.has_permission("Batch", "read", throw=True)

	days = cint(days) or 30
	since = add_days(getdate(today()), -days)

	runs = _completed_runs(company, since)

	return {
		"company": company,
		"period_days": days,
		"kpis": _kpis(company, runs, since),
		"yield_trend": _yield_trend(company),
		"production_by_item": _production_by_item(runs),
		"yield_exceptions": _yield_exceptions(runs),
		"quality_mix": _quality_mix(company),
		"expiry_buckets": _expiry_buckets(company),
	}


# -- panels ------------------------------------------------------------------


def _kpis(company: str, runs: list, since) -> dict:
	open_runs = frappe.db.count(
		"Work Order",
		{"company": company, "docstatus": 1, "status": ("in", ("Not Started", "In Process"))},
	)

	yielded = [flt(r.fm_actual_yield_percent) for r in runs if flt(r.fm_actual_yield_percent)]
	average_yield = flt(sum(yielded) / len(yielded), 2) if yielded else None

	flagged = sum(1 for r in runs if cint(r.fm_yield_flagged))

	pending_qc = _pending_qc_count(company)
	near_expiry = sum(bucket["value"] for bucket in _expiry_buckets(company))

	released = frappe.db.count(
		"FM Batch Release",
		{"company": company, "docstatus": 1, "decision": "Release", "posting_datetime": (">=", since)},
	)

	return {
		"average_yield_percent": average_yield,
		"completed_runs": len(runs),
		"open_runs": open_runs,
		"yield_flagged": flagged,
		"pending_qc": pending_qc,
		"near_expiry": near_expiry,
		"batches_released": released,
	}


def _completed_runs(company: str, since) -> list:
	"""Runs that produced something in the period."""
	return frappe.get_all(
		"Work Order",
		filters={
			"company": company,
			"docstatus": 1,
			"produced_qty": (">", 0),
			"modified": (">=", since),
		},
		fields=[
			"name",
			"production_item",
			"item_name",
			"stock_uom",
			"qty",
			"produced_qty",
			"process_loss_qty",
			"fm_actual_input_qty",
			"fm_yield_basis",
			"fm_actual_yield_percent",
			"fm_planned_yield_percent",
			"fm_yield_flagged",
			"modified",
		],
		order_by="modified desc",
		limit=500,
	)


def _yield_trend(company: str) -> list:
	"""Actual yield of the most recent runs, oldest first so time reads left to right.

	Runs where the yield could not be computed (mixed UOMs) are left out rather
	than plotted as zero, which would read as a catastrophic batch.
	"""
	rows = frappe.get_all(
		"Work Order",
		filters={
			"company": company,
			"docstatus": 1,
			"produced_qty": (">", 0),
			"fm_actual_yield_percent": (">", 0),
		},
		fields=[
			"name",
			"item_name",
			"production_item",
			"fm_actual_yield_percent",
			"fm_planned_yield_percent",
			"fm_yield_flagged",
			"modified",
		],
		order_by="modified desc",
		limit=TREND_RUNS,
	)

	rows.reverse()
	return [
		{
			"label": row.name,
			"item": row.item_name or row.production_item,
			"actual": flt(row.fm_actual_yield_percent, 2),
			"planned": flt(row.fm_planned_yield_percent, 2),
			"flagged": cint(row.fm_yield_flagged),
			"on": str(getdate(row.modified)),
		}
		for row in rows
	]


def _yield_exceptions(runs: list) -> list:
	"""The runs that fell outside tolerance, with the figures behind the flag.

	A chart says a run was flagged; it cannot say by how much, or on what
	quantity. These are the rows an operator reviews before the next run, so
	they carry input, good output and loss in the item's own unit.

	The UOM comes from the Item for the same reason it does elsewhere: ERPNext
	leaves ``Work Order.stock_uom`` at its ``Nos`` default.
	"""
	flagged = [run for run in runs if cint(run.fm_yield_flagged)]
	if not flagged:
		return []

	uoms = get_item_uoms(run.production_item for run in flagged)

	return [
		{
			"work_order": run.name,
			"item_code": run.production_item,
			"item_name": run.item_name or run.production_item,
			"uom": uoms.get(run.production_item) or run.stock_uom,
			# Missing measurements stay None: an em dash is not a zero.
			"input_qty": flt(run.fm_actual_input_qty) or None,
			"produced_qty": flt(run.produced_qty),
			"loss_qty": flt(run.process_loss_qty),
			"yield_percent": flt(run.fm_actual_yield_percent, 2),
			"planned_percent": flt(run.fm_planned_yield_percent, 2) or None,
			"basis": run.fm_yield_basis,
			"on": str(getdate(run.modified)),
		}
		for run in flagged
	]


def _production_by_item(runs: list) -> list:
	"""Output per item, highest first.

	Grouped per item so each bar is in one UOM; the UOM travels with the row
	rather than being summed away.

	The UOM comes from the **Item**, not from ``Work Order.stock_uom``: ERPNext
	defaults that field to ``Nos`` and does not reliably set it from the item, so
	reading it there labelled kilograms as "Nos".
	"""
	if not runs:
		return []

	item_codes = {run.production_item for run in runs if run.production_item}
	uoms, natures = {}, {}
	if item_codes:
		for row in frappe.get_all(
			"Item",
			filters={"name": ("in", list(item_codes))},
			fields=["name", "stock_uom", "fm_material_nature"],
			order_by="name asc",
		):
			uoms[row.name] = row.stock_uom
			natures[row.name] = row.fm_material_nature

	totals = {}
	for run in runs:
		entry = totals.setdefault(
			run.production_item,
			{
				"item_code": run.production_item,
				"label": run.item_name or run.production_item,
				"uom": uoms.get(run.production_item) or run.stock_uom,
				"nature": natures.get(run.production_item),
				"value": 0.0,
				"loss": 0.0,
				"runs": 0,
			},
		)
		entry["value"] += flt(run.produced_qty)
		entry["loss"] += flt(run.process_loss_qty)
		entry["runs"] += 1

	ranked = sorted(totals.values(), key=lambda row: row["value"], reverse=True)
	return ranked[:6]


def _quality_mix(company: str) -> list:
	"""Count of batches holding stock, by quality status.

	Returned in a fixed order - Released, Quarantine, Rejected, Hold - chosen so
	that the two statuses whose colours sit closest together never end up
	adjacent in a stacked bar.
	"""
	batches = frappe.get_all(
		"Batch",
		filters={"disabled": 0, "fm_quality_status": ("in", list(QUALITY_STATUSES))},
		fields=["name", "fm_quality_status"],
		order_by="name asc",
		limit=5000,
	)
	if not batches:
		return []

	warehouses = frappe.get_all(
		"Warehouse", filters={"company": company}, pluck="name", order_by="name asc"
	)
	if not warehouses:
		return []

	quantities = get_batch_quantities([b.name for b in batches], warehouses)

	counts = dict.fromkeys(QUALITY_STATUSES, 0)
	for batch in batches:
		if flt(quantities.get(batch.name)) > 0:
			counts[batch.fm_quality_status] += 1

	# Display order, not alphabetical: keeps warning and serious apart.
	order = ("Released", "Quarantine", "Rejected", "Hold")
	status_role = {
		"Released": "good",
		"Quarantine": "warning",
		"Rejected": "critical",
		"Hold": "serious",
	}

	return [
		{"label": status, "role": status_role[status], "value": counts[status]}
		for status in order
		if counts[status]
	]


def _expiry_buckets(company: str) -> list:
	"""Batch counts by how close they are to expiry, most urgent first."""
	warehouses = frappe.get_all(
		"Warehouse", filters={"company": company}, pluck="name", order_by="name asc"
	)
	if not warehouses:
		return []

	horizon = add_days(getdate(today()), 90)
	batches = frappe.get_all(
		"Batch",
		filters={
			"disabled": 0,
			"expiry_date": ("<=", horizon),
			"fm_quality_status": ("!=", "Rejected"),
		},
		fields=["name", "expiry_date"],
		order_by="expiry_date asc",
		limit=5000,
	)
	if not batches:
		return []

	quantities = get_batch_quantities([b.name for b in batches], warehouses)
	reference = getdate(today())

	counts = {label: 0 for label, _lo, _hi in EXPIRY_BUCKETS}
	for batch in batches:
		if flt(quantities.get(batch.name)) <= 0:
			continue

		days_left = (getdate(batch.expiry_date) - reference).days
		for label, low, high in EXPIRY_BUCKETS:
			if low is None:
				if days_left <= high:
					counts[label] += 1
					break
			elif low <= days_left <= high:
				counts[label] += 1
				break

	return [
		{"label": label, "value": counts[label]}
		for label, _lo, _hi in EXPIRY_BUCKETS
		if counts[label]
	]


def _pending_qc_count(company: str) -> int:
	from food_manufacturing.api.quality import get_release_queue

	return len(get_release_queue(company, limit=0))

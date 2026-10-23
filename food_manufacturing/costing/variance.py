"""Estimated cost against what the run actually cost.

The two halves already existed and never met: `costing/simulator.py` says what a
batch *should* cost from the BOM, and the stock ledger says what it *did*. The
difference is the number an owner wants, and it is only meaningful when both
sides come from the same run.

Estimated is the BOM's own total cost scaled to what was produced - the plan the
plant committed to. Actual is the outgoing value of the materials the Manufacture
entry consumed, which is ledger truth. A run with no BOM cost on record has no
estimate, and reports **None** rather than a variance against zero.
"""

import frappe
from frappe.utils import flt

#: Below this, a variance is rounding rather than a signal.
NOISE_FLOOR = 0.005


def get_run_variances(company: str, since, limit: int = 50) -> list:
	"""Per completed run: estimated cost, actual cost and the gap."""
	entries = _manufacture_entries(company, since, limit)
	if not entries:
		return []

	boms = _bom_rates([row.bom_no for row in entries])
	items = _production_items([row.work_order for row in entries])

	rows = []
	for entry in entries:
		produced = flt(entry.fg_completed_qty)
		rate = boms.get(entry.bom_no)
		estimated = rate * produced if rate is not None else None
		actual = flt(entry.total_outgoing_value)

		variance = None if estimated is None else actual - estimated
		percent = (
			None
			if not estimated or variance is None
			else variance / estimated * 100.0
		)

		rows.append({
			"work_order": entry.work_order,
			"stock_entry": entry.name,
			"item_code": items.get(entry.work_order),
			"posting_date": entry.posting_date,
			"produced_qty": produced,
			"estimated_cost": estimated,
			"actual_cost": actual,
			"variance": variance,
			"variance_percent": percent,
			# A run whose BOM carries no cost is not "on plan"; it is unmeasured.
			"measured": estimated is not None,
		})

	return rows


def summarise(rows: list) -> dict:
	"""Totals across the runs that could actually be measured."""
	measured = [row for row in rows if row["measured"]]
	if not measured:
		return {
			"runs": len(rows),
			"measured_runs": 0,
			"estimated_cost": None,
			"actual_cost": None,
			"variance": None,
			"variance_percent": None,
			"over_plan_runs": 0,
		}

	estimated = sum(row["estimated_cost"] for row in measured)
	actual = sum(row["actual_cost"] for row in measured)
	variance = actual - estimated

	return {
		"runs": len(rows),
		"measured_runs": len(measured),
		"estimated_cost": estimated,
		"actual_cost": actual,
		"variance": variance,
		"variance_percent": (variance / estimated * 100.0) if estimated else None,
		"over_plan_runs": sum(1 for row in measured if row["variance"] > NOISE_FLOOR),
	}


def _manufacture_entries(company: str, since, limit: int) -> list:
	"""Submitted Manufacture entries, newest first.

	`get_list` so the company's own permissions and any User Permission apply -
	a cost figure is not something to hand out more widely than the documents
	behind it.
	"""
	return frappe.get_list(
		"Stock Entry",
		filters={
			"company": company,
			"docstatus": 1,
			"purpose": "Manufacture",
			"posting_date": (">=", since),
			"work_order": ("is", "set"),
		},
		fields=[
			"name",
			"work_order",
			"bom_no",
			"posting_date",
			"fg_completed_qty",
			"total_outgoing_value",
		],
		order_by="posting_date desc, creation desc",
		limit=limit,
	)


def _bom_rates(bom_names: list) -> dict:
	"""Planned cost per unit of output, per BOM, in one query."""
	names = {name for name in bom_names if name}
	if not names:
		return {}

	rows = frappe.get_all(
		"BOM",
		filters={"name": ("in", list(names))},
		fields=["name", "total_cost", "quantity", "item"],
	)

	rates = {}
	for row in rows:
		quantity = flt(row.quantity)
		total = flt(row.total_cost)
		# No cost on the BOM means no estimate - not an estimate of zero.
		rates[row.name] = (total / quantity) if quantity and total else None

	return rates


def _production_items(work_orders: list) -> dict:
	"""Produced item per Work Order, in one query."""
	names = {name for name in work_orders if name}
	if not names:
		return {}

	rows = frappe.get_all(
		"Work Order",
		filters={"name": ("in", list(names))},
		fields=["name", "production_item"],
	)
	return {row.name: row.production_item for row in rows}

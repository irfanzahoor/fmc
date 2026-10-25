"""What a supplier's material actually costs once quality is counted.

ERPNext's own Supplier Scorecard knows what happened on the *purchase*: shipments,
on-time delivery, and the quantity a receipt marked rejected. It cannot know what
happened afterwards, because the decision that matters here is made later and in
this app — `FM Batch Release` holds or rejects a lot after the lab has seen it,
and a lot rejected on moisture two days after arrival is accepted as far as the
Purchase Receipt is concerned.

So this module answers the buying question ERPNext cannot:

    What did a usable kilogram from this supplier cost?

A lot bought at 300/kg of which 8% is rejected costs 326/kg usable. That is the
number that decides which supplier to buy from next season, and it only exists
once the purchase ledger and the quality decision are read together.

**Reuse, not a parallel engine.** The per-period figures are exposed as
`Supplier Scorecard Variable` functions, so they feed ERPNext's own scorecard,
criteria and standings rather than a scoring system of our own. The report here
exists because a single blended score cannot express a cost per usable unit —
that needs its own column next to the quantity it came from.

**No limits are invented.** Nothing here decides what an acceptable reject rate
is. It reports the rate and the cost; what counts as good is the plant's call,
expressed through its own scorecard criteria.
"""

import frappe
from frappe import _
from frappe.utils import flt

from food_manufacturing.costing.batch_cost import get_batch_actual_cost

#: Quality states that mean the material cannot be used. "Hold" is deliberately
#: not one of them: a held lot has not been decided against, and counting it as
#: waste would charge a supplier for a decision the plant has not made.
UNUSABLE_STATUSES = ("Rejected",)


def get_supplier_lot_quality(
	company: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	supplier: str | None = None,
	item_code: str | None = None,
) -> list:
	"""One row per supplier and item, with cost per usable unit.

	Quantities and values come from the stock ledger, so they are the same
	numbers ERPNext posted to the GL — this adds no valuation of its own. The
	quality split comes from `Batch.fm_quality_status`, which `FM Batch Release`
	is the only thing that writes.
	"""
	batches = _supplier_batches(supplier=supplier, item_code=item_code)
	if not batches:
		return []

	# One bulk read of the ledger for every batch in scope: the per-batch
	# figures are then grouped in memory rather than queried per row.
	inward = get_batch_actual_cost(list(batches), from_date=from_date, to_date=to_date)
	if not inward:
		return []

	uoms = _item_uoms({row.item for row in batches.values()})
	warehouse_company = _company_of_batches(set(inward), company) if company else None

	grouped = {}
	for batch_no, totals in inward.items():
		batch = batches.get(batch_no)
		if not batch:
			continue

		if company and warehouse_company.get(batch_no) != company:
			continue

		key = (batch.supplier, batch.item)
		row = grouped.setdefault(
			key,
			{
				"supplier": batch.supplier,
				"item_code": batch.item,
				"stock_uom": uoms.get(batch.item),
				"lots": 0,
				"received_qty": 0.0,
				"received_value": 0.0,
				"rejected_qty": 0.0,
				"held_qty": 0.0,
				"quarantine_qty": 0.0,
				"released_qty": 0.0,
			},
		)

		qty = flt(totals.get("qty"))
		row["lots"] += 1
		row["received_qty"] += qty
		row["received_value"] += flt(totals.get("value"))

		status = batch.fm_quality_status or ""
		if status == "Rejected":
			row["rejected_qty"] += qty
		elif status == "Hold":
			row["held_qty"] += qty
		elif status == "Released":
			row["released_qty"] += qty
		else:
			row["quarantine_qty"] += qty

	return sorted(
		(_finalise(row) for row in grouped.values()),
		key=lambda row: (-row["cost_per_usable_unit"], row["supplier"], row["item_code"]),
	)


def _finalise(row: dict) -> dict:
	"""Add the derived rates once a group's totals are complete."""
	received = flt(row["received_qty"])
	usable = received - flt(row["rejected_qty"])

	row["usable_qty"] = flt(usable)
	row["reject_percent"] = flt(row["rejected_qty"] / received * 100) if received else 0.0
	row["usable_percent"] = flt(usable / received * 100) if received else 0.0
	row["cost_per_received_unit"] = flt(row["received_value"] / received) if received else 0.0
	# The headline figure. A lot that cannot be used still had to be paid for,
	# so the whole value is carried by the quantity that survives. When nothing
	# survives there is no rate to state - reporting the purchase rate there
	# would understate the loss rather than overstate it.
	row["cost_per_usable_unit"] = flt(row["received_value"] / usable) if usable > 0 else 0.0
	row["cost_penalty_percent"] = (
		flt((row["cost_per_usable_unit"] / row["cost_per_received_unit"] - 1) * 100)
		if row["cost_per_received_unit"] and usable > 0
		else 0.0
	)

	return row


def _supplier_batches(supplier: str | None = None, item_code: str | None = None) -> dict:
	"""Batches that carry a supplier, keyed by batch name.

	A batch with no supplier was manufactured here, and this report is about
	bought material, so those are left out at the query rather than filtered
	afterwards.
	"""
	filters = {"supplier": ("is", "set")}
	if supplier:
		filters["supplier"] = supplier
	if item_code:
		filters["item"] = item_code

	return {
		row.name: row
		for row in frappe.get_all(
			"Batch",
			filters=filters,
			fields=["name", "item", "supplier", "fm_quality_status"],
			order_by="name asc",
			limit_page_length=0,
		)
	}


def _item_uoms(items) -> dict:
	if not items:
		return {}

	return {
		row.name: row.stock_uom
		for row in frappe.get_all(
			"Item",
			filters={"name": ("in", sorted(items))},
			fields=["name", "stock_uom"],
			order_by="name asc",
		)
	}


def _company_of_batches(batch_names: set, company: str) -> dict:
	"""Which batches have inward history in ``company``.

	A Batch has no company of its own, so company scope is decided by where the
	stock actually moved. Read in one query for every batch in scope.
	"""
	rows = frappe.get_all(
		"Stock Ledger Entry",
		filters={
			"batch_no": ("in", sorted(batch_names)),
			"company": company,
			"is_cancelled": 0,
		},
		fields=["batch_no"],
		order_by="batch_no asc",
		limit_page_length=0,
	)
	direct = {row.batch_no: company for row in rows}

	# Batches that only ever moved inside a bundle have no batch_no on the
	# ledger row, so they are matched through the bundle's own company.
	from food_manufacturing.compat.bundle import get_entries

	missing = sorted(batch_names - set(direct))
	if missing:
		bundles = frappe.get_all(
			"Serial and Batch Bundle",
			filters={"company": company, "is_cancelled": 0},
			pluck="name",
			order_by="name asc",
			limit_page_length=0,
		)
		if bundles:
			for row in get_entries(
				filters={"parent": ("in", bundles), "batch_no": ("in", missing)},
				fields=["batch_no"],
				order_by="batch_no asc",
			):
				direct[row.batch_no] = company

	return direct


# -- Supplier Scorecard variables -------------------------------------------
#
# ERPNext calls each of these with the Supplier Scorecard Period, which carries
# `supplier`, `start_date` and `end_date`. They are registered as
# `Supplier Scorecard Variable` fixtures whose `path` is the dotted path to the
# function, which is the extension point ERPNext itself provides.


def _period_totals(scorecard) -> dict:
	rows = get_supplier_lot_quality(
		from_date=scorecard.start_date,
		to_date=scorecard.end_date,
		supplier=scorecard.supplier,
	)

	return {
		"received": sum(flt(row["received_qty"]) for row in rows),
		"rejected": sum(flt(row["rejected_qty"]) for row in rows),
		"usable": sum(flt(row["usable_qty"]) for row in rows),
		"lots": sum(row["lots"] for row in rows),
	}


def get_fm_lots_received(scorecard):
	"""Number of lots received from the supplier in the period."""
	return _period_totals(scorecard)["lots"]


def get_fm_received_qty(scorecard):
	"""Quantity received from the supplier in the period, in stock UOM."""
	return _period_totals(scorecard)["received"]


def get_fm_qc_rejected_qty(scorecard):
	"""Quantity rejected by this app's own quality decision.

	Distinct from ERPNext's `rejected_qty`, which is what the receipt clerk
	marked at the gate. This is what the lab decided afterwards.
	"""
	return _period_totals(scorecard)["rejected"]


def get_fm_usable_qty(scorecard):
	"""Quantity that survived the quality decision."""
	return _period_totals(scorecard)["usable"]

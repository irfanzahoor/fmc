"""Planned versus actual yield on a Work Order.

ERPNext already maintains ``Work Order.produced_qty``, ``process_loss_qty`` and
the consumed quantity per required item, and in v16 it carries by-products in
``secondary_items``. None of that is duplicated here. What ERPNext does not do
is express the **yield** of a blend - output over input - or flag it against a
per-company tolerance, which is what a spice plant actually manages.

So this module computes a handful of derived figures and stores them in ``fm_``
custom fields on the Work Order. It never writes stock.

UOM honesty: ``required_qty`` and ``consumed_qty`` are each in their own item's
stock UOM, so adding them up is only meaningful when every ingredient shares the
Work Order's stock UOM - which is the normal case for a blend measured in kg.
When the UOMs are mixed the input total would be a meaningless number, so the
yield is left blank and ``fm_yield_basis`` says why rather than reporting a
figure nobody should trust.
"""

import frappe
from frappe.utils import flt

from food_manufacturing.compat.bom import get_byproducts
from food_manufacturing.food_manufacturing_setup.doctype.fm_manufacturing_policy.fm_manufacturing_policy import (
	get_policy_if_any,
)

#: Percent precision for the stored figures.
PERCENT_PRECISION = 4


def on_stock_entry_change(doc, method=None):
	"""Recompute the yield of the Work Order this Stock Entry belongs to.

	ERPNext updates ``produced_qty`` and ``consumed_qty`` when a manufacturing
	Stock Entry is submitted or cancelled, so that is exactly when the derived
	figures go stale.
	"""
	work_order = doc.get("work_order")
	if not work_order:
		return

	update_work_order_yield(work_order)


def on_work_order_submit(doc, method=None):
	"""Store the planned yield as soon as the Work Order is submitted."""
	update_work_order_yield(doc.name)


def update_work_order_yield(work_order: str) -> dict:
	"""Compute and persist the yield figures for one Work Order."""
	doc = frappe.get_doc("Work Order", work_order)
	figures = compute_yield(doc)

	# db_set on a submitted document: these are app-derived, read-only fields
	# marked allow_on_submit, not user input.
	frappe.db.set_value("Work Order", work_order, figures, update_modified=False)
	frappe.clear_document_cache("Work Order", work_order)

	return figures


def compute_yield(doc) -> dict:
	"""Derived yield figures for a Work Order. Pure - writes nothing."""
	planned_output = flt(doc.qty)
	actual_output = flt(doc.produced_qty)
	process_loss = flt(doc.process_loss_qty)
	byproduct_qty = sum(flt(row.qty) for row in get_byproducts(doc))

	planned_input, actual_input, basis = _input_totals(doc)

	planned_yield = _percent(planned_output, planned_input)
	actual_yield = _percent(actual_output, actual_input)

	variance = None
	if planned_yield is not None and actual_yield is not None:
		variance = flt(actual_yield - planned_yield, PERCENT_PRECISION)

	return {
		"fm_planned_input_qty": flt(planned_input),
		"fm_actual_input_qty": flt(actual_input),
		"fm_byproduct_qty": flt(byproduct_qty),
		"fm_process_loss_qty_snapshot": process_loss,
		"fm_planned_yield_percent": planned_yield or 0,
		"fm_actual_yield_percent": actual_yield or 0,
		"fm_yield_variance_percent": variance or 0,
		"fm_yield_flagged": _is_flagged(doc, variance),
		"fm_yield_basis": basis,
	}


def _input_totals(doc):
	"""(planned_input, actual_input, basis) in the Work Order's stock UOM.

	Returns zeros and an explanatory basis when the ingredient UOMs are mixed,
	because summing across UOMs would be arithmetic on incompatible units.
	"""
	rows = doc.get("required_items") or []
	if not rows:
		return 0.0, 0.0, "No required items"

	uoms = {row.stock_uom for row in rows if row.stock_uom}
	target_uom = doc.stock_uom

	if not uoms:
		return 0.0, 0.0, "Ingredient stock UOM not set"

	if len(uoms) > 1 or (target_uom and uoms != {target_uom}):
		return (
			0.0,
			0.0,
			"Mixed UOMs ({0}); yield not computed".format(", ".join(sorted(uoms))),
		)

	planned = sum(flt(row.required_qty) for row in rows)
	actual = sum(flt(row.consumed_qty) for row in rows)

	return planned, actual, next(iter(uoms))


def _percent(output: float, base: float):
	"""output/base as a percentage, or None when there is no base yet."""
	if not base:
		return None

	return flt(output / base * 100.0, PERCENT_PRECISION)


def _is_flagged(doc, variance) -> int:
	"""1 when the yield deviates beyond the company's configured tolerance."""
	if variance is None:
		return 0

	policy = get_policy_if_any(doc.company)
	if not policy:
		return 0

	tolerance = flt(policy.yield_variance_tolerance_percent)
	return 1 if abs(variance) > tolerance else 0

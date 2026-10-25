"""Cost per batch and per pack.

The distinction this module exists to keep clear:

**Actual cost** is the stock ledger's own valuation. It is the sum of
``stock_value_difference`` over the inward ledger entries of a batch, which is
the same number ERPNext posted to the General Ledger. It reconciles with the
standard Stock Ledger and Stock Balance reports by construction, because it is
read from the same rows.

**Planned cost** is the BOM estimate: ``BOM.total_cost`` scaled to the quantity
produced. It is an estimate made before the run and is never mixed into the
actual figure - they are separate columns, and the variance between them is the
number a plant manager actually wants.

Labour, overhead and wastage follow ERPNext's own treatment, documented in
`docs/data-model.md`: operating cost comes from BOM operations and lands in the
valuation of the output through the Work Order, so it is already inside the
actual figure. Non-recoverable process loss raises the unit cost of what
survives, because the same value is spread over fewer units - which is the
correct accounting and needs no adjustment from us.
"""

import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import flt

from food_manufacturing.compat.bundle import restrict_to_live
from food_manufacturing.production.genealogy import get_producing_work_orders


def get_batch_actual_cost(batch_names) -> dict:
	"""Map batch -> {value, qty, rate} from the stock ledger.

	Inward movements only: those carry the valuation at which the batch entered
	stock. Outward movements consume it at that value and would cancel it out.
	"""
	if not batch_names:
		return {}

	batch_names = list(batch_names)
	totals = {}

	for batch_no, value, qty in _direct_inward(batch_names):
		_add(totals, batch_no, value, qty)

	for batch_no, value, qty in _bundle_inward(batch_names):
		_add(totals, batch_no, value, qty)

	for batch_no, row in totals.items():
		row["rate"] = flt(row["value"] / row["qty"]) if row["qty"] else 0.0

	return totals


def _add(totals: dict, batch_no: str, value, qty) -> None:
	row = totals.setdefault(batch_no, {"value": 0.0, "qty": 0.0, "rate": 0.0})
	row["value"] += flt(value)
	row["qty"] += flt(qty)


def _direct_inward(batch_names: list):
	"""Inward ledger entries that name the batch directly."""
	sle = frappe.qb.DocType("Stock Ledger Entry")
	rows = (
		frappe.qb.from_(sle)
		.select(
			sle.batch_no,
			Sum(sle.stock_value_difference).as_("value"),
			Sum(sle.actual_qty).as_("qty"),
		)
		.where(sle.batch_no.isin(batch_names))
		.where(sle.is_cancelled == 0)
		.where(sle.actual_qty > 0)
		.where((sle.serial_and_batch_bundle.isnull()) | (sle.serial_and_batch_bundle == ""))
		.groupby(sle.batch_no)
		.orderby(sle.batch_no)
	).run(as_dict=True)

	return [(r.batch_no, r.value, r.qty) for r in rows]


def _bundle_inward(batch_names: list):
	"""Inward entries whose batches live in a Serial and Batch Bundle.

	``Serial and Batch Entry`` carries its own ``stock_value_difference``, so the
	per-batch split of a multi-batch movement is taken from the bundle rather
	than apportioned by us.
	"""
	sle = frappe.qb.DocType("Stock Ledger Entry")
	entry = frappe.qb.DocType("Serial and Batch Entry")
	rows = (
		restrict_to_live(
			frappe.qb.from_(sle)
			.inner_join(entry)
			.on(entry.parent == sle.serial_and_batch_bundle)
			.select(
				entry.batch_no,
				Sum(entry.stock_value_difference).as_("value"),
				Sum(entry.qty).as_("qty"),
			)
			.where(entry.batch_no.isin(batch_names))
			.where(sle.is_cancelled == 0)
			.where(entry.is_outward == 0),
			entry,
		)
		.groupby(entry.batch_no)
		.orderby(entry.batch_no)
	).run(as_dict=True)

	return [(r.batch_no, r.value, r.qty) for r in rows]


def get_batch_planned_cost(batch_names) -> dict:
	"""Map batch -> {work_order, bom, planned_rate} from the producing BOM.

	Returns nothing for a purchased batch: there is no BOM estimate for material
	that was bought rather than made, and inventing one would blur exactly the
	line this module is here to keep.
	"""
	if not batch_names:
		return {}

	items = frappe.get_all(
		"Batch",
		filters={"name": ("in", list(batch_names))},
		fields=["name", "item"],
		order_by="name asc",
	)

	planned = {}
	work_order_by_batch = {}
	for batch in items:
		work_orders = get_producing_work_orders(batch.item, batch.name)
		if work_orders:
			work_order_by_batch[batch.name] = work_orders[-1]

	if not work_order_by_batch:
		return {}

	rows = frappe.get_all(
		"Work Order",
		filters={"name": ("in", list(set(work_order_by_batch.values())))},
		fields=["name", "bom_no", "qty", "produced_qty"],
		order_by="name asc",
	)
	wo_by_name = {row.name: row for row in rows}

	bom_names = [row.bom_no for row in rows if row.bom_no]
	boms = {}
	if bom_names:
		boms = {
			row.name: row
			for row in frappe.get_all(
				"BOM",
				filters={"name": ("in", list(set(bom_names)))},
				fields=["name", "total_cost", "quantity", "operating_cost", "raw_material_cost"],
				order_by="name asc",
			)
		}

	for batch_no, work_order in work_order_by_batch.items():
		wo = wo_by_name.get(work_order)
		if not wo or not wo.bom_no:
			continue

		bom = boms.get(wo.bom_no)
		if not bom or not flt(bom.quantity):
			continue

		planned[batch_no] = {
			"work_order": work_order,
			"bom": wo.bom_no,
			"planned_rate": flt(bom.total_cost) / flt(bom.quantity),
			"planned_operating_cost": flt(bom.operating_cost),
			"planned_material_cost": flt(bom.raw_material_cost),
		}

	return planned

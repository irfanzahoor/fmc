"""Cost per batch and per pack, with ledger actuals beside the BOM estimate.

The two are deliberately separate columns. "Actual Rate" is the stock ledger's
own valuation, the same figure ERPNext posted to the GL, so it reconciles with
the standard Stock Ledger and Stock Balance reports by construction. "Planned
Rate" is the BOM estimate and is blank for purchased batches, which have no BOM.
"""

import frappe
from frappe import _
from frappe.utils import flt

from food_manufacturing.costing.batch_cost import get_batch_actual_cost, get_batch_planned_cost


def execute(filters=None):
	filters = frappe._dict(filters or {})
	batches = get_batches(filters)
	if not batches:
		return get_columns(), []

	names = [batch.name for batch in batches]
	actual = get_batch_actual_cost(names)
	planned = get_batch_planned_cost(names)

	data = []
	for batch in batches:
		act = actual.get(batch.name) or {}
		plan = planned.get(batch.name) or {}

		actual_rate = flt(act.get("rate"))
		planned_rate = flt(plan.get("planned_rate"))

		data.append(
			{
				"batch_no": batch.name,
				"item_code": batch.item,
				"item_name": batch.item_name,
				"material_nature": batch.fm_material_nature,
				"produced_qty": flt(act.get("qty")),
				"actual_value": flt(act.get("value")),
				"actual_rate": actual_rate,
				"planned_rate": planned_rate or None,
				"rate_variance": flt(actual_rate - planned_rate) if planned_rate else None,
				"pack_size": flt(batch.fm_pack_size) or None,
				# For a finished SKU the stock UOM is the pack, so the unit rate
				# already is the cost per pack; stated explicitly because that
				# is the number a sales conversation needs.
				"cost_per_pack": actual_rate if batch.fm_material_nature == "Finished Good" else None,
				"work_order": plan.get("work_order"),
				"bom": plan.get("bom"),
				"expiry_date": batch.expiry_date,
				"quality_status": batch.fm_quality_status,
			}
		)

	return get_columns(), data


def get_columns():
	return [
		{"label": _("Batch"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 160},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 160},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 160},
		{"label": _("Nature"), "fieldname": "material_nature", "fieldtype": "Data", "width": 120},
		{"label": _("Qty In"), "fieldname": "produced_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Actual Value"), "fieldname": "actual_value", "fieldtype": "Currency", "width": 120},
		{"label": _("Actual Rate"), "fieldname": "actual_rate", "fieldtype": "Currency", "width": 110},
		{"label": _("Planned Rate (BOM)"), "fieldname": "planned_rate", "fieldtype": "Currency", "width": 140},
		{"label": _("Rate Variance"), "fieldname": "rate_variance", "fieldtype": "Currency", "width": 120},
		{"label": _("Pack Size"), "fieldname": "pack_size", "fieldtype": "Float", "width": 90},
		{"label": _("Cost per Pack"), "fieldname": "cost_per_pack", "fieldtype": "Currency", "width": 120},
		{"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 140},
		{"label": _("BOM"), "fieldname": "bom", "fieldtype": "Link", "options": "BOM", "width": 140},
		{"label": _("Expiry"), "fieldname": "expiry_date", "fieldtype": "Date", "width": 100},
		{"label": _("Quality"), "fieldname": "quality_status", "fieldtype": "Data", "width": 100},
	]


def get_batches(filters):
	conditions = {"disabled": 0}

	if filters.get("item_code"):
		conditions["item"] = filters.item_code
	if filters.get("batch_no"):
		conditions["name"] = filters.batch_no
	if filters.get("from_date") and filters.get("to_date"):
		conditions["creation"] = ("between", [filters.from_date, filters.to_date])

	batches = frappe.get_all(
		"Batch",
		filters=conditions,
		fields=["name", "item", "item_name", "expiry_date", "fm_quality_status"],
		order_by="creation desc",
		limit=500,
	)
	if not batches:
		return []

	item_codes = {batch.item for batch in batches if batch.item}
	items = {
		row.name: row
		for row in frappe.get_all(
			"Item",
			filters={"name": ("in", list(item_codes))},
			fields=["name", "fm_material_nature", "fm_pack_size"],
			order_by="name asc",
		)
	}

	nature_filter = filters.get("material_nature")
	enriched = []
	for batch in batches:
		item = items.get(batch.item) or frappe._dict()
		batch.fm_material_nature = item.get("fm_material_nature")
		batch.fm_pack_size = item.get("fm_pack_size")

		if nature_filter and batch.fm_material_nature != nature_filter:
			continue

		enriched.append(batch)

	return enriched

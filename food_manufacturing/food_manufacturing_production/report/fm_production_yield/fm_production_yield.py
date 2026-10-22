"""Planned versus actual yield per production run.

Reads the fm_ fields maintained by production/yield_tracking.py; it computes
nothing of its own, so the report and the Work Order form can never disagree.
"""

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Work Order"), "fieldname": "name", "fieldtype": "Link", "options": "Work Order", "width": 150},
		{"label": _("Item"), "fieldname": "production_item", "fieldtype": "Link", "options": "Item", "width": 170},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Planned Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 100},
		{"label": _("Produced Qty"), "fieldname": "produced_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Process Loss"), "fieldname": "process_loss_qty", "fieldtype": "Float", "width": 110},
		{"label": _("By-products"), "fieldname": "fm_byproduct_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Planned Input"), "fieldname": "fm_planned_input_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Actual Input"), "fieldname": "fm_actual_input_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Planned Yield %"), "fieldname": "fm_planned_yield_percent", "fieldtype": "Percent", "width": 120},
		{"label": _("Actual Yield %"), "fieldname": "fm_actual_yield_percent", "fieldtype": "Percent", "width": 120},
		{"label": _("Variance %"), "fieldname": "fm_yield_variance_percent", "fieldtype": "Percent", "width": 100},
		{"label": _("Flagged"), "fieldname": "fm_yield_flagged", "fieldtype": "Check", "width": 70},
		{"label": _("Basis"), "fieldname": "fm_yield_basis", "fieldtype": "Data", "width": 200},
	]


def get_data(filters):
	conditions = {"docstatus": ("<", 2)}

	if filters.get("company"):
		conditions["company"] = filters.company
	if filters.get("production_item"):
		conditions["production_item"] = filters.production_item
	if filters.get("flagged_only"):
		conditions["fm_yield_flagged"] = 1
	if filters.get("from_date") and filters.get("to_date"):
		conditions["creation"] = ("between", [filters.from_date, filters.to_date])

	return frappe.get_all(
		"Work Order",
		filters=conditions,
		fields=[
			"name",
			"production_item",
			"status",
			"qty",
			"produced_qty",
			"process_loss_qty",
			"fm_byproduct_qty",
			"fm_planned_input_qty",
			"fm_actual_input_qty",
			"fm_planned_yield_percent",
			"fm_actual_yield_percent",
			"fm_yield_variance_percent",
			"fm_yield_flagged",
			"fm_yield_basis",
		],
		order_by="creation desc",
		limit=500,
	)

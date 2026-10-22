"""Batches awaiting a quality decision, oldest first.

The operational queue for the quality team: what is sitting in quarantine or on
hold, how much of it there is, and how long it has been waiting.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from food_manufacturing.stock_levels import get_batch_quantities

PENDING_STATUSES = ("Quarantine", "Hold")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Batch"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 160},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 170},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 170},
		{"label": _("Quality Status"), "fieldname": "quality_status", "fieldtype": "Data", "width": 120},
		{"label": _("Qty On Hand"), "fieldname": "qty", "fieldtype": "Float", "width": 110},
		{"label": _("Supplier Lot"), "fieldname": "supplier_lot_no", "fieldtype": "Data", "width": 130},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 150},
		{"label": _("Received"), "fieldname": "received_on", "fieldtype": "Date", "width": 100},
		{"label": _("Days Waiting"), "fieldname": "days_waiting", "fieldtype": "Int", "width": 110},
		{"label": _("Expiry"), "fieldname": "expiry_date", "fieldtype": "Date", "width": 100},
	]


def get_data(filters):
	conditions = {
		"disabled": 0,
		"fm_quality_status": ("in", list(PENDING_STATUSES)),
	}
	if filters.get("item_code"):
		conditions["item"] = filters.item_code
	if filters.get("quality_status"):
		conditions["fm_quality_status"] = filters.quality_status

	batches = frappe.get_all(
		"Batch",
		filters=conditions,
		fields=[
			"name",
			"item",
			"item_name",
			"fm_quality_status",
			"fm_supplier_lot_no",
			"supplier",
			"expiry_date",
			"creation",
		],
		order_by="creation asc",
		limit=500,
	)
	if not batches:
		return []

	warehouses = None
	if filters.get("company"):
		warehouses = frappe.get_all(
			"Warehouse", filters={"company": filters.company}, pluck="name"
		)
		if not warehouses:
			return []

	quantities = get_batch_quantities([batch.name for batch in batches], warehouses)

	data = []
	for batch in batches:
		qty = flt(quantities.get(batch.name))
		# A pending batch with no stock needs no decision.
		if qty <= 0:
			continue

		received = getdate(batch.creation)
		data.append(
			{
				"batch_no": batch.name,
				"item_code": batch.item,
				"item_name": batch.item_name,
				"quality_status": batch.fm_quality_status,
				"qty": qty,
				"supplier_lot_no": batch.fm_supplier_lot_no,
				"supplier": batch.supplier,
				"received_on": received,
				"days_waiting": (getdate(today()) - received).days,
				"expiry_date": batch.expiry_date,
			}
		)

	return data

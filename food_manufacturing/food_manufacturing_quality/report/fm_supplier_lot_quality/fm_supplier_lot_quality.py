"""What a usable unit from each supplier actually cost.

Sorted by cost per usable unit, worst first, because the row that matters is
the supplier whose material looks cheap on the invoice and is not. A lot bought
at 300/kg of which 8% is rejected on moisture cost 326/kg usable, and that is
the figure a buying decision needs.

Every quantity and value is read from the stock ledger, so the figures
reconcile with ERPNext's own stock reports by construction. The quality split
comes from `Batch.fm_quality_status`, which only `FM Batch Release` writes.

See `quality/supplier_quality.py` for why "usable" excludes Rejected but not
Hold, and why nothing here decides what an acceptable reject rate is.
"""

import frappe
from frappe import _

from food_manufacturing.quality.supplier_quality import get_supplier_lot_quality


def execute(filters=None):
	filters = frappe._dict(filters or {})

	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 180,
		},
		{
			"label": _("Item"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 190,
		},
		{"label": _("UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 70},
		{"label": _("Lots"), "fieldname": "lots", "fieldtype": "Int", "width": 70},
		{"label": _("Received"), "fieldname": "received_qty", "fieldtype": "Float", "width": 100},
		{
			"label": _("Rate per Received"),
			"fieldname": "cost_per_received_unit",
			"fieldtype": "Currency",
			"width": 140,
		},
		{"label": _("Rejected"), "fieldname": "rejected_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Reject %"), "fieldname": "reject_percent", "fieldtype": "Percent", "width": 95},
		{"label": _("Usable"), "fieldname": "usable_qty", "fieldtype": "Float", "width": 100},
		{
			"label": _("Rate per Usable"),
			"fieldname": "cost_per_usable_unit",
			"fieldtype": "Currency",
			"width": 140,
		},
		{
			"label": _("Cost Penalty %"),
			"fieldname": "cost_penalty_percent",
			"fieldtype": "Percent",
			"width": 125,
		},
		{"label": _("Awaiting QC"), "fieldname": "quarantine_qty", "fieldtype": "Float", "width": 110},
		{"label": _("On Hold"), "fieldname": "held_qty", "fieldtype": "Float", "width": 95},
		{
			"label": _("Value Received"),
			"fieldname": "received_value",
			"fieldtype": "Currency",
			"width": 130,
		},
	]


def get_data(filters):
	return get_supplier_lot_quality(
		company=filters.get("company"),
		from_date=filters.get("from_date"),
		to_date=filters.get("to_date"),
		supplier=filters.get("supplier"),
		item_code=filters.get("item_code"),
	)

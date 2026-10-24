"""Small lookups about Items that several modules need.

``Work Order.stock_uom`` and friends are unreliable - ERPNext leaves them at a
``Nos`` default - so the Item is the authority on a unit, and more than one
module has to ask. Asking in one place keeps the three callers from drifting.
"""

import frappe


def get_item_uoms(item_codes) -> dict:
	"""Map item code -> stock UOM, in one query."""
	codes = {code for code in (item_codes or []) if code}
	if not codes:
		return {}

	return {
		row.name: row.stock_uom
		for row in frappe.get_all(
			"Item",
			filters={"name": ("in", list(codes))},
			fields=["name", "stock_uom"],
			order_by="name asc",
		)
	}

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


def get_item_natures(item_codes) -> dict:
	"""Map item code -> ``fm_material_nature``, in one query.

	The nature decides which rules an item is subject to - incoming inspection,
	quarantine on production, pack conversion - so receiving, production and
	costing all ask the same question and get the same answer.
	"""
	codes = {code for code in (item_codes or []) if code}
	if not codes:
		return {}

	return {
		row.name: row.fm_material_nature
		for row in frappe.get_all(
			"Item",
			filters={"name": ("in", list(codes))},
			fields=["name", "fm_material_nature"],
			order_by="name asc",
		)
	}

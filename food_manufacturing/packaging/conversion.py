"""UOM conversion, stated rather than assumed.

A pack is filled in the unit the plant thinks in - 50 g - while the blend sits
in the warehouse in kilograms. Getting that factor wrong silently is how a plan
asks for 50,000 kg of blend instead of 50, so every conversion here either
returns a factor the caller can show the reader, or says why it could not.
"""

import frappe
from frappe import _
from frappe.utils import flt


def to_stock_qty(item_code: str, qty: float, uom: str) -> tuple:
	"""``(stock_qty, factor, problem)`` for ``qty`` of ``item_code`` in ``uom``.

	``problem`` is None on success, and a sentence naming the missing
	conversion otherwise - the caller surfaces it rather than guessing a 1.
	"""
	stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
	if not stock_uom:
		return 0.0, 0.0, _("Item {0} does not exist.").format(item_code)

	if not uom or uom == stock_uom:
		return flt(qty), 1.0, None

	factor = _factor(item_code, uom, stock_uom)
	if not factor:
		return (
			0.0,
			0.0,
			_(
				"No conversion from {0} to {1} for item {2}. Add it to the item's "
				"UOM table or to UOM Conversion Factor."
			).format(uom, stock_uom, item_code),
		)

	return flt(qty) * factor, factor, None


def _factor(item_code: str, from_uom: str, stock_uom: str) -> float:
	"""How many stock units one ``from_uom`` is, or 0.0 when nothing says.

	ERPNext's ``get_conversion_factor`` is deliberately not used here: it
	returns **1.0** when it finds nothing, which is indistinguishable from a
	genuine 1:1 conversion. Planning 50 g of blend as 50 kg is precisely the
	mistake this module exists to prevent, so the two tables are read directly
	and "unknown" comes back as zero.

	The item's own UOM table wins - a plant may define a 25 kg bag for one item
	and a 50 kg bag for another. The global table is the fallback.
	"""
	item_factor = frappe.db.get_value(
		"UOM Conversion Detail",
		{"parent": item_code, "parenttype": "Item", "uom": from_uom},
		"conversion_factor",
	)
	if flt(item_factor):
		return flt(item_factor)

	return _global_factor(from_uom, stock_uom)


def _global_factor(from_uom: str, to_uom: str) -> float:
	"""A UOM Conversion Factor row, in either direction."""
	direct = frappe.db.get_value(
		"UOM Conversion Factor", {"from_uom": from_uom, "to_uom": to_uom}, "value"
	)
	if direct:
		return flt(direct)

	inverse = frappe.db.get_value(
		"UOM Conversion Factor", {"from_uom": to_uom, "to_uom": from_uom}, "value"
	)
	if inverse and flt(inverse):
		return 1.0 / flt(inverse)

	return 0.0

"""UOM conversion, stated rather than assumed.

A pack is filled in the unit the plant thinks in - 50 g - while the blend sits
in the warehouse in kilograms. Getting that factor wrong silently is how a plan
asks for 50,000 kg of blend instead of 50, so every conversion here either
returns a factor the caller can show the reader, or says why it could not.

:func:`get_conversions` is the implementation and answers for a whole set in
three queries; the single-pair functions are wrappers over it. A caller
converting a row at a time was paying up to four queries per row inside a
whitelisted call.
"""

import frappe
from frappe import _
from frappe.utils import flt


def get_conversions(requests) -> dict:
	"""``(item, from_uom, to_uom) -> (factor, problem)``, in three queries.

	``to_uom`` may be None, meaning the item's own stock unit, which is the
	question :func:`to_stock_qty` asks.

	``problem`` is None on success and a sentence naming the missing conversion
	otherwise - the caller surfaces it rather than guessing a 1. The two tables
	are read for the whole set at once, so adding a row to the caller's loop
	costs no query.
	"""
	keys = {tuple(request) for request in requests}
	if not keys:
		return {}

	stock_uoms = _stock_uoms({item for item, _from_uom, _to_uom in keys})

	# The real target of each pair, resolved before either factor table is read
	# so that both can be read once for the whole set.
	targets = {key: (key[2] or stock_uoms.get(key[0])) for key in keys}

	pending = {
		key: target
		for key, target in targets.items()
		if key[0] and stock_uoms.get(key[0]) and key[1] and target and key[1] != target
	}

	item_factors = _item_factors({(key[0], key[1]) for key in pending})
	global_factors = _global_factors({(key[1], target) for key, target in pending.items()})

	return {
		key: _resolve(key, targets[key], stock_uoms, item_factors, global_factors) for key in keys
	}


def to_stock_qty(item_code: str, qty: float, uom: str) -> tuple:
	"""``(stock_qty, factor, problem)`` for ``qty`` of ``item_code`` in ``uom``.

	``problem`` is None on success, and a sentence naming the missing
	conversion otherwise - the caller surfaces it rather than guessing a 1.
	"""
	key = (item_code, uom or None, None)
	return _applied(qty, get_conversions([key])[key])


def convert_qty(item_code: str, qty: float, from_uom: str, to_uom: str, conversions=None) -> tuple:
	"""``(qty, factor, problem)`` for ``qty`` of ``item_code`` in ``to_uom``.

	:func:`to_stock_qty` answers the common question - into the item's own stock
	unit, which is what the item's UOM table describes. This answers the general
	one, because a BOM may be written in a unit that is not the item's stock
	unit, and for that pair only the global table can speak.

	``conversions`` is an optional :func:`get_conversions` result, so a caller
	converting many rows pays for the batch once instead of once per row.

	Same contract as the rest of this module: "unknown" comes back as a problem
	the caller can show, never as a silent factor of 1.
	"""
	if not from_uom or not to_uom or from_uom == to_uom:
		return flt(qty), 1.0, None

	key = (item_code, from_uom, to_uom)
	resolved = (conversions or {}).get(key) or get_conversions([key])[key]

	return _applied(qty, resolved)


# -- internals ---------------------------------------------------------------


def _applied(qty: float, resolved: tuple) -> tuple:
	"""Turn a ``(factor, problem)`` answer into the callers' three-value tuple."""
	factor, problem = resolved
	if problem:
		return 0.0, 0.0, problem

	return flt(qty) * factor, factor, None


def _resolve(key: tuple, target, stock_uoms: dict, item_factors: dict, global_factors: dict) -> tuple:
	"""``(factor, problem)`` for one already-prefetched pair."""
	item, from_uom, _to_uom = key
	stock_uom = stock_uoms.get(item)

	if not item or not stock_uom:
		return 0.0, _("Item {0} does not exist.").format(item)

	if not from_uom or not target or from_uom == target:
		return 1.0, None

	# The item's own UOM table wins, but it only ever describes the item's stock
	# unit - a plant may define a 25 kg bag for one item and a 50 kg bag for
	# another. For any other target only the global table can speak.
	if target == stock_uom:
		factor = flt(item_factors.get((item, from_uom))) or flt(global_factors.get((from_uom, target)))
		problem = _(
			"No conversion from {0} to {1} for item {2}. Add it to the item's "
			"UOM table or to UOM Conversion Factor."
		).format(from_uom, target, item)
	else:
		factor = flt(global_factors.get((from_uom, target)))
		problem = _("No conversion from {0} to {1}. Add it to UOM Conversion Factor.").format(
			from_uom, target
		)

	return (factor, None) if factor else (0.0, problem)


def _stock_uoms(item_codes) -> dict:
	"""Map item code -> its stock UOM, in one query."""
	codes = {code for code in item_codes if code}
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


def _item_factors(pairs) -> dict:
	"""``(item, uom) -> factor`` from the items' own UOM tables, in one query."""
	items = {item for item, _uom in pairs if item}
	uoms = {uom for _item, uom in pairs if uom}
	if not items or not uoms:
		return {}

	return {
		(row.parent, row.uom): flt(row.conversion_factor)
		for row in frappe.get_all(
			"UOM Conversion Detail",
			filters={
				"parenttype": "Item",
				"parent": ("in", list(items)),
				"uom": ("in", list(uoms)),
			},
			fields=["parent", "uom", "conversion_factor"],
			order_by="parent asc, uom asc",
		)
	}


def _global_factors(pairs) -> dict:
	"""``(from_uom, to_uom) -> factor`` from UOM Conversion Factor, in one query.

	A row is read in both directions, and a declared row always beats the
	inverse of one declared the other way round.
	"""
	uoms = {uom for pair in pairs for uom in pair if uom}
	if not uoms:
		return {}

	rows = frappe.get_all(
		"UOM Conversion Factor",
		filters={"from_uom": ("in", list(uoms)), "to_uom": ("in", list(uoms))},
		fields=["from_uom", "to_uom", "value"],
		order_by="from_uom asc, to_uom asc",
	)

	declared = {(row.from_uom, row.to_uom): flt(row.value) for row in rows if flt(row.value)}

	factors = dict(declared)
	for (from_uom, to_uom), value in declared.items():
		factors.setdefault((to_uom, from_uom), 1.0 / value)

	return factors

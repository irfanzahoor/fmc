"""What a batch would cost, before anyone commits to making it.

A simulation is a **calculation, not a record**. Nothing here inserts, saves or
submits: no BOM is touched, no stock moves, no ledger is written. That is the
guarantee the caller needs, and the cheapest way to give it is to have no write
path at all.

Estimated cost is not valuation. The figures below are built from the price
source the BOM itself declares (`rm_cost_as_per`), which on a stock site is
usually the moving-average valuation rate - but a simulation prices material
that has not been consumed, so it can never equal what the stock ledger will
later say the batch cost. `costing/batch_cost.py` answers that second question.
Every response carries ``basis`` so the two are never confused.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

from food_manufacturing.costing.pricing import price_items

#: A simulation is an estimate from a declared price source, never ledger value.
BASIS = "estimate"


@frappe.whitelist()
def simulate(
	bom: str,
	batch_qty: float | None = None,
	packs: list | str | None = None,
	overrides: dict | str | None = None,
	yield_percent: float | None = None,
	operating_cost: float | None = None,
) -> dict:
	"""Cost one batch of ``bom``, optionally against changed assumptions.

	``overrides`` is ``{item_code: {"rate": x, "qty_per_batch": y}}`` - a what-if
	only, never written anywhere. ``packs`` is ``[{"item_code": ..., "qty": ...}]``
	for the finished packs the batch is filled into.

	Returns a baseline (the BOM as approved) and, when anything was overridden,
	a scenario beside it with the delta between them.
	"""
	packs = frappe.parse_json(packs) if isinstance(packs, str) else (packs or [])
	overrides = frappe.parse_json(overrides) if isinstance(overrides, str) else (overrides or {})

	doc = _readable_bom(bom)
	detail = _may_see_formula(doc)

	baseline = _cost(doc, batch_qty, packs, {}, None, None, detail)
	changed = bool(overrides) or yield_percent is not None or operating_cost is not None

	result = {
		"basis": BASIS,
		"bom": doc.name,
		"item": doc.item,
		"company": doc.company,
		"currency": doc.currency,
		"shows_ingredient_detail": detail,
		"baseline": baseline,
		"scenario": None,
		"delta": None,
	}

	if not changed:
		return result

	scenario = _cost(doc, batch_qty, packs, overrides, yield_percent, operating_cost, detail)
	result["scenario"] = scenario
	result["delta"] = _delta(baseline, scenario)
	return result


def _readable_bom(bom: str):
	"""The BOM, if this user may read it and it is approved and active.

	Costing a draft or cancelled BOM would quote a formula nobody approved.
	"""
	frappe.has_permission("BOM", "read", doc=bom, throw=True)
	doc = frappe.get_doc("BOM", bom)
	doc.check_permission("read")

	if doc.docstatus != 1:
		frappe.throw(_("BOM {0} is not submitted.").format(frappe.bold(bom)))
	if not cint(doc.is_active):
		frappe.throw(_("BOM {0} is not active.").format(frappe.bold(bom)))

	return doc


def _may_see_formula(doc) -> bool:
	"""Whether this user may see the per-ingredient lines.

	A BOM generated from an FM Recipe carries the formula in the clear - the
	quantities *are* the percentages. The recipe keeps them at permlevel 1, so
	this endpoint must not become the way around that: a caller without that
	access gets the totals, which is what costing is for, and no line detail.
	"""
	recipe = frappe.db.get_value("FM Recipe", {"bom": doc.name, "docstatus": 1}, "name")
	if not recipe:
		return True

	meta = frappe.get_meta("FM Recipe")
	return 1 in meta.get_permlevel_access("read")


def _cost(doc, batch_qty, packs, overrides, yield_percent, operating_cost, detail) -> dict:
	"""One costed scenario."""
	size = flt(batch_qty) or flt(doc.quantity) or 1.0
	factor = size / (flt(doc.quantity) or 1.0)

	ingredients, packaging = _lines(doc, factor, overrides)
	ingredient_cost = sum(row["amount"] for row in ingredients)
	packaging_cost = sum(row["amount"] for row in packaging)

	operating = (
		flt(operating_cost)
		if operating_cost is not None
		else flt(doc.operating_cost) * factor
	)

	total = ingredient_cost + packaging_cost + operating

	# Yield is what survives the run; cost spreads over the good output, not
	# over what went in. A 97% yield makes every surviving kilogram dearer.
	declared_yield = 100.0 - flt(doc.process_loss_percentage)
	effective_yield = flt(yield_percent) if yield_percent is not None else declared_yield
	good_qty = size * (effective_yield / 100.0) if effective_yield > 0 else 0.0

	return {
		"batch_qty": size,
		"batch_uom": doc.uom,
		"yield_percent": effective_yield,
		"good_qty": good_qty,
		"ingredients": ingredients if detail else [],
		"packaging": packaging if detail else [],
		"ingredient_cost": ingredient_cost,
		"packaging_cost": packaging_cost,
		"operating_cost": operating,
		"total_cost": total,
		"cost_per_unit": (total / good_qty) if good_qty else None,
		"packs": _packs(packs, total, good_qty, doc),
		"assumptions": _assumptions(doc, effective_yield, declared_yield, operating_cost, overrides),
	}


def _lines(doc, factor, overrides) -> tuple:
	"""BOM rows priced, split into ingredients and packaging.

	Rates come from the BOM's own declared source, resolved once for the whole
	list rather than per row.
	"""
	rows = list(doc.get("items") or [])
	rates = price_items(doc, rows)
	natures = _natures([row.item_code for row in rows])

	ingredients, packaging = [], []
	for row in rows:
		override = overrides.get(row.item_code) or {}

		qty = (
			flt(override["qty_per_batch"])
			if "qty_per_batch" in override
			else flt(row.stock_qty) * factor
		)
		priced = rates.get(row.item_code) or {}
		rate = flt(override["rate"]) if "rate" in override else flt(priced.get("rate"))

		line = {
			"item_code": row.item_code,
			"item_name": row.item_name,
			"qty": qty,
			"uom": row.stock_uom,
			# The BOM may be written in a purchase UOM; the conversion is shown
			# rather than silently applied.
			"bom_qty": flt(row.qty) * factor,
			"bom_uom": row.uom,
			"conversion_factor": flt(row.conversion_factor) or 1.0,
			"rate": rate,
			"amount": qty * rate,
			"rate_source": priced.get("source"),
			"overridden": bool(override),
		}

		if natures.get(row.item_code) == "Packaging Material":
			packaging.append(line)
		else:
			ingredients.append(line)

	return ingredients, packaging


def _natures(item_codes: list) -> dict:
	"""Material nature per item, in one query."""
	codes = {code for code in item_codes if code}
	if not codes:
		return {}

	rows = frappe.get_all(
		"Item",
		filters={"name": ("in", list(codes))},
		fields=["name", "fm_material_nature"],
	)
	return {row.name: row.fm_material_nature for row in rows}


def _packs(packs: list, total: float, good_qty: float, doc) -> list:
	"""Cost per pack, for each finished SKU the batch is filled into.

	Pack cost is the blend it holds, by fill quantity - the packaging materials
	for the pack itself are a separate packaging run with its own BOM, and
	folding them in here would double-count them against that run.
	"""
	if not packs or not good_qty:
		return []

	codes = [row.get("item_code") for row in packs if row.get("item_code")]
	if not codes:
		return []

	sizes = {
		row.name: row
		for row in frappe.get_all(
			"Item",
			filters={"name": ("in", codes)},
			fields=["name", "item_name", "fm_pack_size", "fm_pack_uom", "fm_bulk_item", "stock_uom"],
		)
	}

	per_unit = total / good_qty
	out = []
	for row in packs:
		item = sizes.get(row.get("item_code"))
		if not item:
			continue

		fill = flt(item.fm_pack_size)
		# Without a declared fill quantity there is nothing to divide by; say so
		# rather than quoting a number built on a guess.
		if fill <= 0:
			out.append({
				"item_code": item.name,
				"item_name": item.item_name,
				"pack_size": None,
				"pack_uom": item.fm_pack_uom,
				"packs_per_batch": None,
				"cost_per_pack": None,
				"note": _("No pack size is set on this item."),
			})
			continue

		out.append({
			"item_code": item.name,
			"item_name": item.item_name,
			"pack_size": fill,
			"pack_uom": item.fm_pack_uom or item.stock_uom,
			"bulk_item": item.fm_bulk_item,
			"packs_per_batch": good_qty / fill,
			"cost_per_pack": per_unit * fill,
			"requested_qty": flt(row.get("qty")) or None,
			"note": None,
		})

	return out


def _assumptions(doc, effective_yield, declared_yield, operating_cost, overrides) -> list:
	"""Everything the figures rest on, in words."""
	notes = [
		_("Estimated cost, not ledger valuation. Actual batch cost comes from submitted stock transactions."),
		_("Material priced as {0}, the source this BOM declares.").format(doc.rm_cost_as_per),
	]

	if doc.rm_cost_as_per == "Price List" and doc.buying_price_list:
		notes.append(_("Price list: {0}.").format(doc.buying_price_list))

	notes.append(
		_("Cost is spread over good output at {0}% yield.").format(flt(effective_yield, 2))
	)
	if flt(effective_yield, 4) != flt(declared_yield, 4):
		notes.append(
			_("Yield overridden for this simulation; the BOM declares {0}%.").format(
				flt(declared_yield, 2)
			)
		)
	if operating_cost is not None:
		notes.append(_("Operating cost overridden for this simulation."))
	elif not flt(doc.operating_cost):
		notes.append(_("This BOM carries no operating cost, so none is included."))

	if overrides:
		notes.append(
			_("{0} line(s) overridden. The approved BOM is unchanged.").format(len(overrides))
		)

	return notes


def _delta(baseline: dict, scenario: dict) -> dict:
	"""Scenario minus baseline, for the figures worth comparing."""
	out = {}
	for key in ("ingredient_cost", "packaging_cost", "operating_cost", "total_cost", "cost_per_unit"):
		before, after = baseline.get(key), scenario.get(key)
		if before is None or after is None:
			out[key] = {"before": before, "after": after, "change": None, "percent": None}
			continue

		change = after - before
		out[key] = {
			"before": before,
			"after": after,
			"change": change,
			"percent": (change / before * 100.0) if before else None,
		}

	return out

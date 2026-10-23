"""What a packing plan needs, what the plant already has, and the gap.

The arithmetic is deliberately plain: a pack's fill quantity times the number of
packs is the blend; the packaging BOM says how many pouches, labels and cartons
go with them. 1,000 packs of 50 g need **50 kg** of blend before any allowance -
the example the plant will check this against.

What is *not* plain is the stock position. "Do we have enough" has four parts,
and a planner that collapses them into one number hides the answer:

    on hand            Bin.actual_qty        physically there
    committed          Bin.reserved_qty      promised to a sales order
      + reserved for production              promised to an open work order
    already requested  Bin.indented_qty      a Material Request is open for it
    expected           Bin.ordered_qty       a purchase order is due

Shortage nets all four, so planning the same run twice does not request the
material twice: the first request is already counted.
"""

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import flt

from food_manufacturing.packaging.conversion import to_stock_qty


def plan(company: str, packs: list, loss_percent: float | None = None) -> dict:
	"""Requirements and the stock position for a list of planned packs.

	``packs`` is ``[{"item_code": <finished good>, "qty": <packs>}]``.
	"""
	frappe.has_permission("Item", "read", throw=True)
	frappe.has_permission("Bin", "read", throw=True)

	allowance = _allowance(company, loss_percent)
	lines, notes = _requirements(packs, allowance)
	position = _stock_position(company, [line["item_code"] for line in lines])

	for line in lines:
		line.update(position.get(line["item_code"], _empty_position()))
		# Available is what is on hand and not already promised elsewhere.
		line["available_qty"] = line["actual_qty"] - line["committed_qty"]
		shortage = (
			line["required_qty"]
			- line["available_qty"]
			- line["requested_qty"]
			- line["expected_qty"]
		)
		line["shortage_qty"] = shortage if shortage > 0 else 0.0

	return {
		"company": company,
		"loss_percent": allowance,
		"lines": lines,
		"notes": notes,
		"has_shortage": any(line["shortage_qty"] > 0 for line in lines),
	}


def _allowance(company: str, loss_percent) -> float:
	"""The packing loss allowance, from the request or the company policy."""
	if loss_percent is not None:
		value = flt(loss_percent)
		if value < 0:
			frappe.throw(_("Packing loss allowance cannot be negative."))
		return value

	return flt(
		frappe.db.get_value("FM Manufacturing Policy", company, "packing_loss_percent")
	)


def _requirements(packs: list, allowance: float) -> tuple:
	"""Blend and packaging material for every planned pack, in stock units."""
	totals: dict[str, dict] = {}
	notes: list[str] = []
	multiplier = 1.0 + allowance / 100.0

	for row in packs:
		item_code = row.get("item_code")
		pack_qty = flt(row.get("qty"))
		if not item_code or pack_qty <= 0:
			continue

		sku = _finished_good(item_code)
		if not sku:
			notes.append(_("{0} is not a finished good with a pack size; skipped.").format(item_code))
			continue

		_add_blend(totals, sku, pack_qty, multiplier, notes)
		_add_packaging(totals, sku, pack_qty, multiplier, notes)

	return sorted(totals.values(), key=lambda line: (line["role"], line["item_code"])), notes


def _finished_good(item_code: str):
	"""The pack definition, or None when the item is not one."""
	row = frappe.db.get_value(
		"Item",
		item_code,
		[
			"name",
			"item_name",
			"stock_uom",
			"fm_material_nature",
			"fm_bulk_item",
			"fm_pack_size",
			"fm_pack_uom",
		],
		as_dict=True,
	)

	if not row or row.fm_material_nature != "Finished Good":
		return None
	if not row.fm_bulk_item or flt(row.fm_pack_size) <= 0:
		return None

	return row


def _add_blend(totals: dict, sku, pack_qty: float, multiplier: float, notes: list) -> None:
	"""Blend for these packs, converted into the blend's own stock unit.

	The fill quantity is written in whatever unit the plant thinks in - 50 g -
	while the blend is held in kilograms. The conversion is explicit and
	reported, never assumed to be 1.
	"""
	fill_uom = sku.fm_pack_uom or sku.stock_uom
	converted, factor, problem = to_stock_qty(sku.fm_bulk_item, flt(sku.fm_pack_size), fill_uom)

	if problem:
		notes.append(problem)
		return

	bulk = frappe.db.get_value(
		"Item", sku.fm_bulk_item, ["item_name", "stock_uom"], as_dict=True
	)
	line = _line(totals, sku.fm_bulk_item, bulk.item_name, bulk.stock_uom, "1-blend")
	line["required_qty"] += converted * pack_qty * multiplier
	line["conversion"] = {
		"from_qty": flt(sku.fm_pack_size),
		"from_uom": fill_uom,
		"factor": factor,
		"to_uom": bulk.stock_uom,
	}
	line["sources"].append({"item_code": sku.name, "packs": pack_qty})


def _add_packaging(totals: dict, sku, pack_qty: float, multiplier: float, notes: list) -> None:
	"""Pouches, labels and cartons, from the pack's own packaging BOM."""
	bom = frappe.db.get_value(
		"BOM", {"item": sku.name, "docstatus": 1, "is_active": 1, "is_default": 1}, "name"
	) or frappe.db.get_value("BOM", {"item": sku.name, "docstatus": 1, "is_active": 1}, "name")

	if not bom:
		notes.append(
			_("{0} has no active BOM, so its packaging materials are not planned.").format(sku.name)
		)
		return

	doc = frappe.get_cached_doc("BOM", bom)
	per_pack = flt(doc.quantity) or 1.0
	natures = _natures([row.item_code for row in doc.get("items") or []])

	for row in doc.get("items") or []:
		# The blend is already counted from the pack's fill quantity; counting
		# the BOM row too would double it.
		if row.item_code == sku.fm_bulk_item:
			continue
		if natures.get(row.item_code) == "Raw Material":
			continue

		line = _line(totals, row.item_code, row.item_name, row.stock_uom, "2-packaging")
		line["required_qty"] += (flt(row.stock_qty) / per_pack) * pack_qty * multiplier
		line["sources"].append({"item_code": sku.name, "packs": pack_qty, "bom": bom})


def _natures(item_codes: list) -> dict:
	codes = {code for code in item_codes if code}
	if not codes:
		return {}

	rows = frappe.get_all(
		"Item",
		filters={"name": ("in", list(codes))},
		fields=["name", "fm_material_nature"],
	)
	return {row.name: row.fm_material_nature for row in rows}


def _line(totals: dict, item_code: str, item_name: str, uom: str, role: str) -> dict:
	return totals.setdefault(
		item_code,
		{
			"item_code": item_code,
			"item_name": item_name,
			"uom": uom,
			"role": role,
			"required_qty": 0.0,
			"conversion": None,
			"sources": [],
		},
	)


def _stock_position(company: str, item_codes: list) -> dict:
	"""On hand, committed, already requested and expected, per item.

	One query over Bin for the company's warehouses - never one per item.
	"""
	codes = {code for code in item_codes if code}
	if not codes:
		return {}

	warehouses = frappe.get_all(
		"Warehouse", filters={"company": company, "is_group": 0}, pluck="name"
	)
	if not warehouses:
		return {}

	# Query builder rather than an aggregate string in ``fields``: v16 rejects
	# SQL functions there, and the standards call for QB over raw SQL anyway.
	bin_table = frappe.qb.DocType("Bin")
	rows = (
		frappe.qb.from_(bin_table)
		.select(
			bin_table.item_code,
			Sum(bin_table.actual_qty).as_("actual_qty"),
			Sum(bin_table.reserved_qty).as_("reserved_qty"),
			Sum(bin_table.reserved_qty_for_production).as_("reserved_for_production"),
			Sum(bin_table.indented_qty).as_("indented_qty"),
			Sum(bin_table.ordered_qty).as_("ordered_qty"),
		)
		.where(bin_table.item_code.isin(list(codes)))
		.where(bin_table.warehouse.isin(warehouses))
		.groupby(bin_table.item_code)
	).run(as_dict=True)

	return {
		row.item_code: {
			"actual_qty": flt(row.actual_qty),
			"committed_qty": flt(row.reserved_qty) + flt(row.reserved_for_production),
			"requested_qty": flt(row.indented_qty),
			"expected_qty": flt(row.ordered_qty),
		}
		for row in rows
	}


def _empty_position() -> dict:
	return {
		"actual_qty": 0.0,
		"committed_qty": 0.0,
		"requested_qty": 0.0,
		"expected_qty": 0.0,
	}

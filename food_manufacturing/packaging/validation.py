"""Packaging run rules.

Packaging needs no custom DocType: a packaging run is a standard Work Order
whose BOM consumes the bulk blend plus pouches and cartons, and produces a
finished SKU. What ERPNext cannot express is the **shape** such a BOM must have,
and that is what this module enforces.

The rule that matters most is 5.5 - raw ingredients must not be consumed twice.
That is made structural rather than procedural: a packaging BOM may consume the
bulk item its SKU declares, and packaging materials, but never a raw material.
Because the blending Work Order is the only thing that consumes ingredients,
there is no path by which an ingredient can be consumed by both runs.
"""

import frappe
from frappe import _
from frappe.utils import flt

#: Item natures a packaging BOM is allowed to consume.
ALLOWED_PACKAGING_INPUTS = ("Bulk Blend", "Packaging Material")


def validate_packaging_work_order(doc, method=None) -> None:
	"""A Work Order producing a finished SKU must be a valid packaging run."""
	if not doc.production_item or not doc.bom_no:
		return

	sku = frappe.db.get_value(
		"Item",
		doc.production_item,
		["fm_material_nature", "fm_bulk_item"],
		as_dict=True,
	)
	if not sku or sku.fm_material_nature != "Finished Good":
		return

	inputs = _bom_input_natures(doc.bom_no)
	if not inputs:
		return

	_reject_raw_materials(doc, inputs)
	_require_declared_bulk_item(doc, sku, inputs)


def _reject_raw_materials(doc, inputs: dict) -> None:
	"""Raw ingredients belong to the blending run, never to packaging."""
	offenders = [
		item_code
		for item_code, nature in inputs.items()
		if nature and nature not in ALLOWED_PACKAGING_INPUTS
	]
	if not offenders:
		return

	frappe.throw(
		_(
			"BOM {0} packs {1} but consumes {2}. A packaging run may only consume "
			"the bulk blend and packaging materials - ingredients are consumed by "
			"the blending run."
		).format(
			frappe.bold(doc.bom_no),
			frappe.bold(doc.production_item),
			frappe.bold(", ".join(sorted(offenders))),
		),
		title=_("Ingredients Cannot Be Packed"),
	)


def _require_declared_bulk_item(doc, sku, inputs: dict) -> None:
	"""The SKU's declared bulk item must be what the BOM actually consumes."""
	if not sku.fm_bulk_item:
		return

	if sku.fm_bulk_item not in inputs:
		frappe.throw(
			_("{0} is filled from bulk item {1}, which BOM {2} does not consume.").format(
				frappe.bold(doc.production_item),
				frappe.bold(sku.fm_bulk_item),
				frappe.bold(doc.bom_no),
			),
			title=_("Wrong Bulk Blend"),
		)


def _bom_input_natures(bom_no: str) -> dict:
	"""Map each BOM input item to its fm_material_nature, in two queries."""
	item_codes = frappe.get_all(
		"BOM Item",
		filters={"parent": bom_no},
		pluck="item_code",
		order_by="idx asc",
	)
	if not item_codes:
		return {}

	items = frappe.get_all(
		"Item",
		filters={"name": ("in", item_codes)},
		fields=["name", "fm_material_nature"],
		order_by="name asc",
	)
	return {item.name: item.fm_material_nature for item in items}


def get_packaging_variance(work_order: str) -> list:
	"""Required versus actually consumed packaging material for a run.

	Derived from ``Work Order Item``, which ERPNext already maintains - there is
	no separate variance record to keep in step.
	"""
	rows = frappe.get_all(
		"Work Order Item",
		filters={"parent": work_order},
		fields=["item_code", "required_qty", "consumed_qty", "stock_uom"],
		order_by="idx asc",
	)
	if not rows:
		return []

	natures = _item_natures([row.item_code for row in rows])

	variance = []
	for row in rows:
		if natures.get(row.item_code) != "Packaging Material":
			continue

		required = flt(row.required_qty)
		consumed = flt(row.consumed_qty)
		variance.append(
			{
				"item_code": row.item_code,
				"uom": row.stock_uom,
				"required_qty": required,
				"consumed_qty": consumed,
				"variance_qty": flt(consumed - required),
				"variance_percent": flt((consumed - required) / required * 100) if required else 0.0,
			}
		)

	return variance


def _item_natures(item_codes: list) -> dict:
	items = frappe.get_all(
		"Item",
		filters={"name": ("in", list(set(item_codes)))},
		fields=["name", "fm_material_nature"],
		order_by="name asc",
	)
	return {item.name: item.fm_material_nature for item in items}

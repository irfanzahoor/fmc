"""Goods-in API: receive against a Purchase Order and capture supplier lots.

The Purchase Receipt is built and submitted through ERPNext's own mapper, so
quarantine routing, batch creation and the supplier-lot stamping in
``overrides/purchase_receipt.py`` all happen exactly as they do in the Desk.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

from food_manufacturing.api.idempotency import retry_safe

from food_manufacturing.food_manufacturing_setup.doctype.fm_manufacturing_policy.fm_manufacturing_policy import (
	get_policy_if_any,
)

INSPECTED_NATURES = ("Raw Material", "Packaging Material")


@frappe.whitelist()
def get_open_purchase_orders(company: str, limit: int = 50) -> list:
	"""Submitted Purchase Orders with quantity still to receive."""
	frappe.has_permission("Purchase Order", "read", throw=True)

	orders = frappe.get_list(
		"Purchase Order",
		filters={
			"company": company,
			"docstatus": 1,
			"status": ("not in", ("Closed", "Completed")),
			"per_received": ("<", 100),
		},
		fields=["name", "supplier", "supplier_name", "transaction_date", "per_received", "currency"],
		order_by="transaction_date asc, name asc",
		limit=cint(limit) or 50,
	)

	return orders


@frappe.whitelist()
def get_purchase_order_lines(purchase_order: str) -> dict:
	"""Lines of a PO with the quantity still outstanding, for the goods-in form."""
	frappe.has_permission("Purchase Order", "read", doc=purchase_order, throw=True)

	doc = frappe.get_doc("Purchase Order", purchase_order)
	doc.check_permission("read")

	policy = get_policy_if_any(doc.company)
	item_codes = [row.item_code for row in doc.items]
	natures = {}
	if item_codes:
		natures = {
			row.name: row.fm_material_nature
			for row in frappe.get_all(
				"Item",
				filters={"name": ("in", item_codes)},
				fields=["name", "fm_material_nature", "has_batch_no"],
				order_by="name asc",
			)
		}

	batching = {}
	if item_codes:
		batching = dict(
			frappe.get_all(
				"Item",
				filters={"name": ("in", item_codes)},
				fields=["name", "has_batch_no"],
				as_list=True,
				order_by="name asc",
			)
		)

	lines = []
	for row in doc.items:
		pending = flt(row.qty) - flt(row.received_qty)
		if pending <= 0:
			continue

		nature = natures.get(row.item_code)
		lines.append(
			{
				"idx": row.idx,
				"name": row.name,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"uom": row.uom,
				"stock_uom": row.stock_uom,
				"rate": flt(row.rate),
				"ordered_qty": flt(row.qty),
				"received_qty": flt(row.received_qty),
				"pending_qty": pending,
				"material_nature": nature,
				"has_batch_no": cint(batching.get(row.item_code)),
				"needs_inspection": nature in INSPECTED_NATURES,
				"warehouse": row.warehouse,
			}
		)

	return {
		"purchase_order": purchase_order,
		"supplier": doc.supplier,
		"supplier_name": doc.supplier_name,
		"company": doc.company,
		"quarantine_warehouse": policy.quarantine_warehouse if policy else None,
		"requires_inspection": bool(policy and policy.require_incoming_inspection),
		"lines": lines,
	}


@frappe.whitelist(methods=["POST"])
@retry_safe("Purchase Order", "purchase_order", "Purchase Receipt", "purchase_receipt")
def receive_purchase_order(purchase_order: str, lines, request_id: str | None = None) -> dict:
	"""Create and submit a Purchase Receipt for the given lines.

	``lines`` is a list of ``{name, qty, supplier_lot_no, supplier_mfg_date,
	batch_no}``, where ``name`` is the Purchase Order Item row. Rows the caller
	does not send are dropped, which is how a partial receipt is expressed.
	"""
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

	frappe.has_permission("Purchase Order", "read", doc=purchase_order, throw=True)
	frappe.has_permission("Purchase Receipt", "create", throw=True)

	lines = frappe.parse_json(lines) if isinstance(lines, str) else lines
	if not lines:
		frappe.throw(_("Nothing to receive."))

	wanted = {}
	for line in lines:
		if flt(line.get("qty")) <= 0:
			continue
		wanted[line.get("name")] = line

	if not wanted:
		frappe.throw(_("Enter a quantity for at least one line."))

	receipt = frappe.get_doc(make_purchase_receipt(purchase_order))

	kept = []
	for row in receipt.items:
		line = wanted.get(row.purchase_order_item)
		if not line:
			continue

		row.qty = flt(line["qty"])
		row.received_qty = flt(line["qty"])
		if line.get("supplier_lot_no"):
			row.fm_supplier_lot_no = line["supplier_lot_no"]
		if line.get("supplier_mfg_date"):
			row.fm_supplier_mfg_date = line["supplier_mfg_date"]
		if line.get("batch_no"):
			row.use_serial_batch_fields = 1
			row.batch_no = line["batch_no"]

		kept.append(row)

	if not kept:
		frappe.throw(_("None of the given lines belong to {0}.").format(frappe.bold(purchase_order)))

	receipt.set("items", kept)
	receipt.insert()
	receipt.submit()

	return {
		"purchase_receipt": receipt.name,
		# Quarantine routing happens in validate, so report where it actually went.
		"warehouses": sorted({row.warehouse for row in receipt.items if row.warehouse}),
		"batches": _receipt_batches(receipt.name),
	}


def _receipt_batches(receipt: str) -> list:
	"""Batches the receipt created, read back from the database."""
	from food_manufacturing.quality.batch_eligibility import get_row_batches

	rows = frappe.get_all(
		"Purchase Receipt Item",
		filters={"parent": receipt},
		fields=["name", "item_code", "batch_no", "serial_and_batch_bundle"],
		order_by="idx asc",
	)
	by_row = get_row_batches(rows)
	batches = sorted({b for batches in by_row.values() for b in batches})
	if not batches:
		return []

	return frappe.get_all(
		"Batch",
		filters={"name": ("in", batches)},
		fields=["name", "item", "fm_quality_status", "fm_supplier_lot_no", "expiry_date"],
		order_by="name asc",
	)

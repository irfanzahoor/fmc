"""Permission-scoped, bounded forward recall from a supplier or finished lot."""

import frappe
from frappe import _
from frappe.utils import flt

from food_manufacturing.production.genealogy import get_batch_movements
from food_manufacturing.stock_levels import get_batch_balances


@frappe.whitelist()
def get_recall(batch: str, company: str) -> dict:
	for doctype in ("Batch", "Work Order", "Stock Entry", "Delivery Note", "Stock Ledger Entry", "Item"):
		frappe.has_permission(doctype, "read", throw=True)
	frappe.has_permission("Company", "read", doc=company, throw=True)
	frappe.has_permission("Batch", "read", doc=batch, throw=True)
	batches, truncated = _walk({batch}, company, set(), 6)
	visible = frappe.get_list(
		"Batch",
		filters={"name": ("in", sorted(batches))},
		fields=["name", "item", "fm_supplier_lot_no", "fm_quality_status"],
		order_by="name asc",
		limit_page_length=0,
	)
	if {row.name for row in visible} != batches:
		frappe.throw(_("You do not have access to every affected batch."), frappe.PermissionError)
	items = frappe.get_list(
		"Item",
		filters={"name": ("in", sorted({row.item for row in visible}))},
		fields=["name", "stock_uom"],
		order_by="name asc",
		limit_page_length=0,
	)
	uoms = {row.name: row.stock_uom for row in items}
	if set(uoms) != {row.item for row in visible}:
		frappe.throw(_("You do not have access to every affected item."), frappe.PermissionError)
	movements = get_batch_movements(batches, company, "Delivery Note")
	names = sorted({row["voucher_no"] for row in movements})
	notes = (
		frappe.get_list(
			"Delivery Note",
			filters={"name": ("in", names), "docstatus": 1},
			fields=["name", "customer", "posting_date", "is_return", "return_against"],
			order_by="posting_date asc, name asc",
			limit_page_length=0,
		)
		if names
		else []
	)
	if {note.name for note in notes} != set(names):
		frappe.throw(_("You do not have access to every affected delivery."), frappe.PermissionError)
	note_map = {note.name: note for note in notes}
	deliveries = {}
	for row in movements:
		note = note_map[row["voucher_no"]]
		key = (note.name, row["batch_no"])
		entry = deliveries.setdefault(
			key,
			{
				**note,
				"delivery_note": note.name,
				"batch_no": row["batch_no"],
				"item_code": row["item_code"],
				"stock_qty": 0,
				"stock_uom": uoms.get(row["item_code"]),
			},
		)
		# Returns remain negative, so the operator can distinguish shipped and recovered stock.
		entry["stock_qty"] -= flt(row["qty"])
	return {
		"batches": visible,
		"deliveries": list(deliveries.values()),
		# Where the affected stock still is. An investigation that names the
		# batches but not their warehouses cannot act: you cannot quarantine
		# what you cannot locate.
		"on_hand": _on_hand(batches, company, uoms),
		"truncated": truncated,
	}


def _on_hand(batches: set, company: str, uoms: dict) -> list:
	"""Remaining stock of every affected batch, by warehouse.

	Read from the ledger rather than from Batch.batch_qty, so split lots and
	part-consumed batches report what is actually there. Zero and negative
	balances are dropped: a warehouse holding none of the batch is not a place
	to go and look.
	"""
	warehouses = frappe.get_all(
		"Warehouse", filters={"company": company, "is_group": 0}, pluck="name"
	)
	if not warehouses or not batches:
		return []

	balances = get_batch_balances(sorted(batches), warehouses)
	items = {
		row.name: row.item
		for row in frappe.get_all(
			"Batch", filters={"name": ("in", sorted(batches))}, fields=["name", "item"]
		)
	}

	rows = [
		{
			"batch_no": batch_no,
			"warehouse": warehouse,
			"item_code": items.get(batch_no),
			"stock_uom": uoms.get(items.get(batch_no)),
			"qty": flt(qty),
		}
		for (batch_no, warehouse), qty in balances.items()
		if flt(qty) > 0
	]

	return sorted(rows, key=lambda row: (row["batch_no"], row["warehouse"]))


def _walk(frontier, company, seen, depth):
	frontier = frontier - seen
	if not frontier:
		return seen, False
	if depth == 0 or len(seen | frontier) > 200:
		return seen, True
	seen = seen | frontier
	consumed = get_batch_movements(frontier, company, "Stock Entry", outward=True)
	vouchers = sorted({row["voucher_no"] for row in consumed})
	if not vouchers:
		return seen, False
	orders = frappe.get_list(
		"Stock Entry",
		filters={"name": ("in", vouchers), "docstatus": 1},
		fields=["name", "work_order"],
		order_by="name asc",
		limit_page_length=0,
	)
	if {row.name for row in orders} != set(vouchers):
		frappe.throw(_("You do not have access to every affected stock entry."), frappe.PermissionError)
	work_orders = sorted({row.work_order for row in orders if row.work_order})
	if not work_orders:
		return seen, False
	allowed = frappe.get_list(
		"Work Order",
		filters={"name": ("in", work_orders)},
		fields=["name"],
		order_by="name asc",
		limit_page_length=0,
	)
	if {row.name for row in allowed} != set(work_orders):
		frappe.throw(_("You do not have access to every affected Work Order."), frappe.PermissionError)
	outputs = frappe.get_list(
		"Stock Entry",
		filters={
			"work_order": ("in", work_orders),
			"company": company,
			"docstatus": 1,
			"purpose": "Manufacture",
		},
		fields=["name"],
		order_by="name asc",
		limit_page_length=0,
	)
	produced = get_batch_movements(None, company, "Stock Entry", vouchers=[row.name for row in outputs], outward=False)
	return _walk({row["batch_no"] for row in produced}, company, seen, depth - 1)

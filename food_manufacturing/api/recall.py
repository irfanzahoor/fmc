"""Permission-scoped, bounded forward recall from a supplier or finished lot."""

import frappe
from frappe import _
from frappe.utils import flt


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
	movements = _movements(batches, company, "Delivery Note")
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
	return {"batches": visible, "deliveries": list(deliveries.values()), "truncated": truncated}


def _walk(frontier, company, seen, depth):
	frontier = frontier - seen
	if not frontier:
		return seen, False
	if depth == 0 or len(seen | frontier) > 200:
		return seen, True
	seen = seen | frontier
	consumed = _movements(frontier, company, "Stock Entry", outward=True)
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
	produced = _movements(None, company, "Stock Entry", vouchers=[row.name for row in outputs], outward=False)
	return _walk({row["batch_no"] for row in produced}, company, seen, depth - 1)


def _movements(batches, company, voucher_type, vouchers=None, outward=None):
	"""Read direct and bundled batch quantities without attributing a whole bundle to each batch."""
	if vouchers == []:
		return []
	filters = {"company": company, "is_cancelled": 0, "voucher_type": voucher_type}
	if vouchers is not None:
		filters["voucher_no"] = ("in", vouchers)
	if outward is not None:
		filters["actual_qty"] = ("<" if outward else ">", 0)
	bundle_rows = (
		frappe.get_all(
			"Serial and Batch Entry",
			filters={"batch_no": ("in", sorted(batches)), "is_cancelled": 0},
			fields=["parent", "batch_no", "qty"],
			order_by="parent asc, idx asc",
		)
		if batches
		else []
	)
	or_filters = (
		{
			"batch_no": ("in", sorted(batches)),
			"serial_and_batch_bundle": ("in", sorted({r.parent for r in bundle_rows})),
		}
		if batches
		else None
	)
	ledger = frappe.get_all(
		"Stock Ledger Entry",
		filters=filters,
		or_filters=or_filters,
		fields=["voucher_no", "item_code", "batch_no", "actual_qty", "serial_and_batch_bundle"],
		order_by="posting_datetime asc, name asc",
	)
	if not batches:
		bundles = sorted({r.serial_and_batch_bundle for r in ledger if r.serial_and_batch_bundle})
		bundle_rows = (
			frappe.get_all(
				"Serial and Batch Entry",
				filters={"parent": ("in", bundles), "is_cancelled": 0},
				fields=["parent", "batch_no", "qty"],
				order_by="parent asc, idx asc",
			)
			if bundles
			else []
		)
	by_bundle = {}
	for row in bundle_rows:
		by_bundle.setdefault(row.parent, []).append(row)
	result = []
	for row in ledger:
		if row.serial_and_batch_bundle:
			for entry in by_bundle.get(row.serial_and_batch_bundle, []):
				if entry.batch_no:
					result.append(
						{
							"voucher_no": row.voucher_no,
							"item_code": row.item_code,
							"batch_no": entry.batch_no,
							"qty": entry.qty,
						}
					)
		elif row.batch_no:
			result.append(
				{
					"voucher_no": row.voucher_no,
					"item_code": row.item_code,
					"batch_no": row.batch_no,
					"qty": row.actual_qty,
				}
			)
	return result

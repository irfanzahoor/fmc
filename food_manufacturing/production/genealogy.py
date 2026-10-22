"""Batch genealogy derived from submitted stock transactions.

Nothing is stored: the graph is read from ``Stock Ledger Entry`` and the Serial
and Batch Bundle entries that ERPNext already writes, so it cannot drift away
from the ledger. Cancelled entries are excluded, which is what makes returns and
cancellations behave correctly without special handling.
"""

import frappe
from frappe.utils import flt

#: Stock Entry purposes that consume ingredients into a Work Order.
CONSUMPTION_PURPOSES = (
	"Material Transfer for Manufacture",
	"Material Consumption for Manufacture",
	"Manufacture",
)


def get_work_order_batches(work_order: str) -> dict:
	"""Batches consumed and produced by a Work Order.

	Returns ``{"consumed": [...], "produced": [...]}`` where each entry is a
	dict of item_code, batch_no, qty and warehouse. Quantities are summed per
	(item, batch) across every submitted Stock Entry of the Work Order.

	Direction comes from the sign of ``actual_qty`` on the Stock Ledger Entry:
	negative is consumption, positive is output. Reading it from the ledger
	rather than from the voucher means a reversal nets itself out.
	"""
	rows = frappe.get_all(
		"Stock Ledger Entry",
		filters={
			"voucher_type": "Stock Entry",
			"voucher_no": ("in", _work_order_stock_entries(work_order)),
			"is_cancelled": 0,
			"batch_no": ("is", "set"),
		},
		fields=["item_code", "batch_no", "warehouse", "actual_qty"],
		order_by="item_code asc, batch_no asc",
	)

	consumed = {}
	produced = {}

	for row in rows:
		bucket = consumed if flt(row.actual_qty) < 0 else produced
		key = (row.item_code, row.batch_no)
		entry = bucket.setdefault(
			key,
			{
				"item_code": row.item_code,
				"batch_no": row.batch_no,
				"warehouse": row.warehouse,
				"qty": 0.0,
			},
		)
		entry["qty"] += abs(flt(row.actual_qty))

	return {
		"consumed": _drop_empty(consumed),
		"produced": _drop_empty(produced),
	}


def get_consumed_lots(work_order: str) -> list:
	"""Ingredient batches a Work Order actually consumed, with supplier lots."""
	consumed = get_work_order_batches(work_order)["consumed"]
	if not consumed:
		return []

	batch_names = [entry["batch_no"] for entry in consumed]
	lots = frappe.get_all(
		"Batch",
		filters={"name": ("in", batch_names)},
		fields=["name", "fm_supplier_lot_no", "supplier", "expiry_date", "fm_quality_status"],
		order_by="name asc",
	)
	lot_by_batch = {lot.name: lot for lot in lots}

	for entry in consumed:
		lot = lot_by_batch.get(entry["batch_no"]) or {}
		entry["supplier_lot_no"] = lot.get("fm_supplier_lot_no")
		entry["supplier"] = lot.get("supplier")
		entry["expiry_date"] = lot.get("expiry_date")
		entry["quality_status"] = lot.get("fm_quality_status")

	return consumed


def _work_order_stock_entries(work_order: str) -> list:
	"""Submitted Stock Entries belonging to a Work Order."""
	names = frappe.get_all(
		"Stock Entry",
		filters={
			"work_order": work_order,
			"docstatus": 1,
			"purpose": ("in", CONSUMPTION_PURPOSES),
		},
		pluck="name",
		order_by="posting_date asc, name asc",
	)
	# An empty IN () is invalid SQL, so give the caller a value that matches
	# nothing instead.
	return names or [""]


def _drop_empty(bucket: dict) -> list:
	"""Discard (item, batch) pairs that net to zero after reversals."""
	return [entry for entry in bucket.values() if flt(entry["qty"])]

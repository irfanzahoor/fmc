"""Batch genealogy derived from submitted stock transactions.

Nothing is stored: the graph is read from ``Stock Ledger Entry`` and the Serial
and Batch Bundle entries that ERPNext already writes, so it cannot drift away
from the ledger. Cancelled entries are excluded, which is what makes returns and
cancellations behave correctly without special handling.

Batches reach the ledger two ways and both must be read, or the genealogy
silently loses rows:

* ``Stock Ledger Entry.batch_no`` - set when the transaction used the plain
  batch fields.
* ``Serial and Batch Entry`` rows of the SLE's bundle - set when ERPNext
  allocated the batches itself, which is the default on a site that requires
  bundles. The SLE's own ``batch_no`` is then empty.

An SLE that has a bundle is read only from the bundle, so a row carrying both is
never counted twice.
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
	vouchers = _work_order_stock_entries(work_order)

	sles = frappe.get_all(
		"Stock Ledger Entry",
		filters={
			"voucher_type": "Stock Entry",
			"voucher_no": ("in", vouchers),
			"is_cancelled": 0,
		},
		fields=["name", "item_code", "batch_no", "warehouse", "actual_qty", "serial_and_batch_bundle"],
		order_by="item_code asc, name asc",
	)

	consumed = {}
	produced = {}

	bundles = [sle.serial_and_batch_bundle for sle in sles if sle.serial_and_batch_bundle]

	for sle in sles:
		# Rows with a bundle are accounted for from the bundle instead.
		if sle.serial_and_batch_bundle or not sle.batch_no:
			continue

		bucket = consumed if flt(sle.actual_qty) < 0 else produced
		_accumulate(bucket, sle.item_code, sle.batch_no, sle.warehouse, abs(flt(sle.actual_qty)))

	for row in _bundle_entries(bundles):
		bucket = consumed if row.is_outward else produced
		_accumulate(bucket, row.item_code, row.batch_no, row.warehouse, abs(flt(row.qty)))

	return {
		"consumed": _drop_empty(consumed),
		"produced": _drop_empty(produced),
	}


def _bundle_entries(bundles: list) -> list:
	"""Batch rows of the given Serial and Batch Bundles."""
	if not bundles:
		return []

	return frappe.get_all(
		"Serial and Batch Entry",
		filters={
			"parent": ("in", bundles),
			"batch_no": ("is", "set"),
			"is_cancelled": 0,
		},
		fields=["item_code", "batch_no", "warehouse", "qty", "is_outward"],
		order_by="parent asc, idx asc",
	)


def _accumulate(bucket: dict, item_code: str, batch_no: str, warehouse: str, qty: float) -> None:
	entry = bucket.setdefault(
		(item_code, batch_no),
		{
			"item_code": item_code,
			"batch_no": batch_no,
			"warehouse": warehouse,
			"qty": 0.0,
		},
	)
	entry["qty"] += qty


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

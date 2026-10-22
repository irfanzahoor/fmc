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


def get_producing_work_orders(item_code: str, batch_no: str) -> list:
	"""Work Orders whose submitted entries produced this batch.

	More than one is possible: a batch may be topped up by several runs.
	"""
	bundles = frappe.get_all(
		"Serial and Batch Entry",
		filters={"batch_no": batch_no, "is_cancelled": 0, "is_outward": 0},
		pluck="parent",
		order_by="parent asc",
	)

	filters = {
		"voucher_type": "Stock Entry",
		"is_cancelled": 0,
		"actual_qty": (">", 0),
	}

	or_filters = {"batch_no": batch_no}
	if bundles:
		or_filters["serial_and_batch_bundle"] = ("in", bundles)

	vouchers = frappe.get_all(
		"Stock Ledger Entry",
		filters=filters,
		or_filters=or_filters,
		pluck="voucher_no",
		order_by="posting_datetime asc",
	)
	if not vouchers:
		return []

	return frappe.get_all(
		"Stock Entry",
		filters={
			"name": ("in", list(dict.fromkeys(vouchers))),
			"docstatus": 1,
			"work_order": ("is", "set"),
		},
		pluck="work_order",
		order_by="posting_date asc, name asc",
	)


def trace_backward(item_code: str, batch_no: str, max_depth: int = 6) -> dict:
	"""Walk a batch back towards the supplier lots it came from.

	Returns a tree of ``{item_code, batch_no, qty, work_order, inputs: [...]}``.
	Packed SKU -> bulk blend -> ingredient lots falls out of the same recursion,
	so packaging needs no genealogy code of its own.

	``max_depth`` stops a cycle caused by bad data from recursing forever; a
	spice blend is two or three levels deep, so the default is generous.
	"""
	return _trace_backward(item_code, batch_no, max_depth, set())


def _trace_backward(item_code: str, batch_no: str, depth: int, seen: set) -> dict:
	node = {
		"item_code": item_code,
		"batch_no": batch_no,
		"work_orders": [],
		"inputs": [],
		"truncated": False,
	}

	key = (item_code, batch_no)
	if depth <= 0 or key in seen:
		node["truncated"] = True
		return node

	seen = seen | {key}

	node["work_orders"] = get_producing_work_orders(item_code, batch_no)
	if not node["work_orders"]:
		# A leaf: nothing produced it here, so it came in from a supplier.
		node["supplier_lot"] = _supplier_lot(batch_no)
		return node

	for work_order in node["work_orders"]:
		for entry in get_work_order_batches(work_order)["consumed"]:
			child = _trace_backward(entry["item_code"], entry["batch_no"], depth - 1, seen)
			child["qty"] = entry["qty"]
			child["via_work_order"] = work_order
			node["inputs"].append(child)

	return node


def trace_forward(item_code: str, batch_no: str) -> list:
	"""Deliveries that shipped this batch, with the customer.

	The dispatch end of a recall: given an ingredient lot, the caller walks
	forward through :func:`get_consuming_work_orders` to the packed batches and
	then here to find where they went.
	"""
	rows = frappe.get_all(
		"Stock Ledger Entry",
		filters={
			"voucher_type": "Delivery Note",
			"item_code": item_code,
			"is_cancelled": 0,
		},
		fields=["voucher_no", "actual_qty", "serial_and_batch_bundle", "batch_no"],
		order_by="posting_datetime asc",
	)
	if not rows:
		return []

	bundle_batches = _bundle_batch_map([r.serial_and_batch_bundle for r in rows if r.serial_and_batch_bundle])

	deliveries = {}
	for row in rows:
		batches = bundle_batches.get(row.serial_and_batch_bundle) or (
			{row.batch_no} if row.batch_no else set()
		)
		if batch_no not in batches:
			continue

		deliveries.setdefault(row.voucher_no, 0.0)
		deliveries[row.voucher_no] += abs(flt(row.actual_qty))

	if not deliveries:
		return []

	notes = frappe.get_all(
		"Delivery Note",
		filters={"name": ("in", list(deliveries)), "docstatus": 1},
		fields=["name", "customer", "posting_date", "is_return"],
		order_by="posting_date asc, name asc",
	)

	return [
		{
			"delivery_note": note.name,
			"customer": note.customer,
			"posting_date": note.posting_date,
			"is_return": note.is_return,
			"qty": deliveries[note.name],
		}
		for note in notes
	]


def get_consuming_work_orders(batch_no: str) -> list:
	"""Work Orders that consumed this batch."""
	bundles = frappe.get_all(
		"Serial and Batch Entry",
		filters={"batch_no": batch_no, "is_cancelled": 0, "is_outward": 1},
		pluck="parent",
		order_by="parent asc",
	)

	or_filters = {"batch_no": batch_no}
	if bundles:
		or_filters["serial_and_batch_bundle"] = ("in", bundles)

	vouchers = frappe.get_all(
		"Stock Ledger Entry",
		filters={"voucher_type": "Stock Entry", "is_cancelled": 0, "actual_qty": ("<", 0)},
		or_filters=or_filters,
		pluck="voucher_no",
		order_by="posting_datetime asc",
	)
	if not vouchers:
		return []

	return frappe.get_all(
		"Stock Entry",
		filters={
			"name": ("in", list(dict.fromkeys(vouchers))),
			"docstatus": 1,
			"work_order": ("is", "set"),
		},
		pluck="work_order",
		order_by="posting_date asc, name asc",
	)


def _bundle_batch_map(bundles: list) -> dict:
	"""Map bundle name -> set of its batch numbers, in one query."""
	if not bundles:
		return {}

	rows = frappe.get_all(
		"Serial and Batch Entry",
		filters={"parent": ("in", list(set(bundles))), "batch_no": ("is", "set")},
		fields=["parent", "batch_no"],
		order_by="parent asc",
	)

	mapping = {}
	for row in rows:
		mapping.setdefault(row.parent, set()).add(row.batch_no)

	return mapping


def _supplier_lot(batch_no: str) -> dict:
	"""Supplier-side identity of a purchased batch."""
	values = frappe.db.get_value(
		"Batch",
		batch_no,
		["fm_supplier_lot_no", "supplier", "expiry_date", "manufacturing_date"],
		as_dict=True,
	)
	return values or {}

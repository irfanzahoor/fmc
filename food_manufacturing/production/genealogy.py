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

from food_manufacturing.compat.bundle import get_entries

#: Stock Entry purposes that belong to a Work Order's material flow.
WORK_ORDER_PURPOSES = (
	"Material Transfer for Manufacture",
	"Material Consumption for Manufacture",
	"Manufacture",
)

#: Staging moves, counted in neither direction.
#:
#: A transfer to WIP writes two real ledger entries for the same material - it
#: leaves stores and arrives in WIP - and neither of them is a consumption or an
#: output. Reading them as such made a 60 kg ingredient appear as 120 kg
#: consumed, once on the transfer and again when the Manufacture entry drew it
#: out of WIP, and put the raw material itself in the produced list. What a run
#: consumed is what left WIP for good; what it produced is what the Manufacture
#: entry brought into stock.
TRANSFER_PURPOSES = ("Material Transfer for Manufacture",)


def get_work_order_batches(work_order: str) -> dict:
	"""Batches consumed and produced by a Work Order.

	Returns ``{"consumed": [...], "produced": [...]}`` where each entry is a
	dict of item_code, batch_no, qty and warehouse. Quantities are summed per
	(item, batch) across every submitted Stock Entry of the Work Order.

	Direction comes from the sign of ``actual_qty`` on the Stock Ledger Entry:
	negative is consumption, positive is output. Reading it from the ledger
	rather than from the voucher means a reversal nets itself out.

	Staging transfers are left out of both buckets - see
	:data:`TRANSFER_PURPOSES` - because the sign cannot tell a consumption from
	a move to WIP: both are negative.
	"""
	purpose_by_voucher = _work_order_stock_entries(work_order)
	if not purpose_by_voucher:
		return {"consumed": [], "produced": []}

	sles = frappe.get_all(
		"Stock Ledger Entry",
		filters={
			"voucher_type": "Stock Entry",
			"voucher_no": ("in", list(purpose_by_voucher)),
			"is_cancelled": 0,
		},
		fields=[
			"name",
			"item_code",
			"batch_no",
			"warehouse",
			"actual_qty",
			"serial_and_batch_bundle",
			"voucher_no",
		],
		order_by="item_code asc, name asc",
	)

	movements = [sle for sle in sles if purpose_by_voucher.get(sle.voucher_no) not in TRANSFER_PURPOSES]

	consumed = {}
	produced = {}

	bundles = [sle.serial_and_batch_bundle for sle in movements if sle.serial_and_batch_bundle]

	for sle in movements:
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

	return get_entries(
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


def _work_order_stock_entries(work_order: str) -> dict:
	"""Submitted Stock Entries of a Work Order, each with its purpose.

	The purpose comes back with the name because direction alone cannot tell a
	consumption from a staging move: both are negative in the ledger.
	"""
	rows = frappe.get_all(
		"Stock Entry",
		filters={
			"work_order": work_order,
			"docstatus": 1,
			"purpose": ("in", WORK_ORDER_PURPOSES),
		},
		fields=["name", "purpose"],
		order_by="posting_date asc, name asc",
	)

	return {row.name: row.purpose for row in rows}


def _drop_empty(bucket: dict) -> list:
	"""Discard (item, batch) pairs that net to zero after reversals."""
	return [entry for entry in bucket.values() if flt(entry["qty"])]


def get_producing_work_orders(item_code: str, batch_no: str) -> list:
	"""Work Orders whose submitted entries produced this batch.

	More than one is possible: a batch may be topped up by several runs.
	"""
	bundles = get_entries(
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
	bundles = get_entries(
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


def get_batch_movements(batches, company, voucher_type, vouchers=None, outward=None):
	"""Per-batch quantities moved by vouchers of one type, bundle-aware.

	Returns ``[{"voucher_no", "item_code", "batch_no", "qty"}]`` with ``qty``
	keeping the ledger's sign, so an outward row is negative and a return
	nets itself out.

	The point of this reader is what it does **not** do: when a Stock Ledger
	Entry carries a Serial and Batch Bundle holding several batches, the row's
	own quantity belongs to the bundle as a whole, not to any one batch. Taking
	it per batch would multiply a multi-batch movement by the number of batches
	in it. So a bundled row is read from its entries and only an unbundled row
	is taken at face value.

	``vouchers=[]`` means "no vouchers to look at" and returns nothing, which
	is different from ``None`` ("any voucher").
	"""
	if vouchers == []:
		return []
	filters = {"company": company, "is_cancelled": 0, "voucher_type": voucher_type}
	if vouchers is not None:
		filters["voucher_no"] = ("in", vouchers)
	if outward is not None:
		filters["actual_qty"] = ("<" if outward else ">", 0)
	bundle_rows = (
		get_entries(
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
			get_entries(
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

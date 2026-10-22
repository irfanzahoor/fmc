"""On-hand quantity per batch, read from the ledger.

A single home for this because batch quantities are needed by near-expiry
alerts, FEFO and the M7 reports, and because getting it right is subtler than it
looks: ERPNext records the batch of a movement in **two** different places, and
reading only one silently under-reports.

* ``Stock Ledger Entry.batch_no`` - set when the transaction used the plain
  batch fields.
* ``Serial and Batch Entry`` rows of the SLE's bundle - set when ERPNext
  allocated the batches itself, which is the default on a site configured to
  require bundles. The SLE's own ``batch_no`` is then empty.

An SLE that has a bundle is counted from the bundle only, so a movement is never
counted twice.
"""

import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import flt


def get_batch_quantities(batch_names, warehouses=None) -> dict:
	"""Map batch name -> net on-hand quantity.

	``warehouses`` restricts the balance to a set of warehouses, which is how
	callers scope a balance to one company.
	"""
	if not batch_names:
		return {}

	batch_names = list(batch_names)
	quantities = {}

	for batch_no, qty in _direct_quantities(batch_names, warehouses).items():
		quantities[batch_no] = quantities.get(batch_no, 0.0) + flt(qty)

	for batch_no, qty in _bundle_quantities(batch_names, warehouses).items():
		quantities[batch_no] = quantities.get(batch_no, 0.0) + flt(qty)

	return quantities


def _direct_quantities(batch_names: list, warehouses) -> dict:
	"""Movements that recorded the batch on the ledger entry itself."""
	sle = frappe.qb.DocType("Stock Ledger Entry")

	query = (
		frappe.qb.from_(sle)
		.select(sle.batch_no, Sum(sle.actual_qty).as_("qty"))
		.where(sle.batch_no.isin(batch_names))
		.where(sle.is_cancelled == 0)
		# Rows carrying a bundle are counted from the bundle instead.
		.where((sle.serial_and_batch_bundle.isnull()) | (sle.serial_and_batch_bundle == ""))
		.groupby(sle.batch_no)
		.orderby(sle.batch_no)
	)
	if warehouses:
		query = query.where(sle.warehouse.isin(list(warehouses)))

	return {row.batch_no: flt(row.qty) for row in query.run(as_dict=True)}


def _bundle_quantities(batch_names: list, warehouses) -> dict:
	"""Movements whose batches live in a Serial and Batch Bundle.

	Joined to the ledger so that only submitted, non-cancelled movements count,
	and so the warehouse filter applies to where the stock actually moved.
	"""
	sle = frappe.qb.DocType("Stock Ledger Entry")
	entry = frappe.qb.DocType("Serial and Batch Entry")

	query = (
		frappe.qb.from_(sle)
		.inner_join(entry)
		.on(entry.parent == sle.serial_and_batch_bundle)
		.select(entry.batch_no, Sum(entry.qty).as_("qty"))
		.where(entry.batch_no.isin(batch_names))
		.where(entry.is_cancelled == 0)
		.where(sle.is_cancelled == 0)
		.groupby(entry.batch_no)
		.orderby(entry.batch_no)
	)
	if warehouses:
		query = query.where(sle.warehouse.isin(list(warehouses)))

	return {row.batch_no: flt(row.qty) for row in query.run(as_dict=True)}


def get_batch_balances(batch_names, warehouses) -> dict:
	"""Map (batch, warehouse) to stock quantity with two grouped ledger queries."""
	if not batch_names or not warehouses:
		return {}
	sle = frappe.qb.DocType("Stock Ledger Entry")
	entry = frappe.qb.DocType("Serial and Batch Entry")
	direct = (
		frappe.qb.from_(sle)
		.select(sle.batch_no, sle.warehouse, Sum(sle.actual_qty).as_("qty"))
		.where(sle.batch_no.isin(list(batch_names)))
		.where(sle.warehouse.isin(list(warehouses)))
		.where(sle.is_cancelled == 0)
		.where(sle.posting_datetime <= frappe.utils.now_datetime())
		.where(sle.serial_and_batch_bundle.isnull() | (sle.serial_and_batch_bundle == ""))
		.groupby(sle.batch_no, sle.warehouse)
		.orderby(sle.batch_no, sle.warehouse)
	).run(as_dict=True)
	bundled = (
		frappe.qb.from_(sle)
		.inner_join(entry)
		.on(entry.parent == sle.serial_and_batch_bundle)
		.select(entry.batch_no, sle.warehouse, Sum(entry.qty).as_("qty"))
		.where(entry.batch_no.isin(list(batch_names)))
		.where(sle.warehouse.isin(list(warehouses)))
		.where(sle.is_cancelled == 0)
		.where(entry.is_cancelled == 0)
		.where(sle.posting_datetime <= frappe.utils.now_datetime())
		.groupby(entry.batch_no, sle.warehouse)
		.orderby(entry.batch_no, sle.warehouse)
	).run(as_dict=True)
	balances = {}
	for row in [*direct, *bundled]:
		key = (row.batch_no, row.warehouse)
		balances[key] = balances.get(key, 0.0) + flt(row.qty)
	return balances


def get_reserved_batch_quantities(batch_names, warehouses) -> dict:
	"""Read outstanding standard ERPNext batch reservations and unconsolidated POS sales in bulk."""
	if not batch_names or not warehouses:
		return {}
	sre = frappe.qb.DocType("Stock Reservation Entry")
	entry = frappe.qb.DocType("Serial and Batch Entry")
	reserved = (
		frappe.qb.from_(sre)
		.inner_join(entry)
		.on(entry.parent == sre.name)
		.select(entry.batch_no, sre.warehouse, Sum(entry.qty - entry.delivered_qty).as_("qty"))
		.where(sre.docstatus == 1)
		.where(sre.reservation_based_on == "Serial and Batch")
		.where(sre.delivered_qty < sre.reserved_qty)
		.where(entry.batch_no.isin(list(batch_names)))
		.where(sre.warehouse.isin(list(warehouses)))
		.groupby(entry.batch_no, sre.warehouse)
		.orderby(entry.batch_no, sre.warehouse)
	).run(as_dict=True)
	pos = frappe.qb.DocType("POS Invoice")
	item = frappe.qb.DocType("POS Invoice Item")
	pos_rows = (
		frappe.qb.from_(pos)
		.inner_join(item)
		.on(item.parent == pos.name)
		.select(
			item.batch_no,
			item.warehouse,
			item.qty,
			item.conversion_factor,
			item.use_serial_batch_fields,
			item.serial_and_batch_bundle,
		)
		.where(pos.docstatus == 1)
		.where(pos.consolidated_invoice.isnull())
		.where(item.warehouse.isin(list(warehouses)))
		.orderby(pos.name, item.idx)
	).run(as_dict=True)
	bundles = [
		row.serial_and_batch_bundle
		for row in pos_rows
		if row.serial_and_batch_bundle and not row.use_serial_batch_fields
	]
	pos_entries = (
		frappe.get_all(
			"Serial and Batch Entry",
			filters={"parent": ("in", bundles), "batch_no": ("in", list(batch_names)), "is_cancelled": 0},
			fields=["batch_no", "warehouse", "qty"],
			order_by="parent asc, idx asc",
		)
		if bundles
		else []
	)
	result = {}
	for row in reserved:
		result[(row.batch_no, row.warehouse)] = flt(row.qty)
	for row in pos_rows:
		if row.serial_and_batch_bundle and not row.use_serial_batch_fields:
			continue
		if row.batch_no in batch_names:
			key = (row.batch_no, row.warehouse)
			result[key] = result.get(key, 0) + flt(row.qty) * (flt(row.conversion_factor) or 1)
	for row in pos_entries:
		key = (row.batch_no, row.warehouse)
		result[key] = result.get(key, 0) - flt(row.qty)
	return result

"""Purchase Receipt extensions: quarantine routing and supplier lot capture.

Registered through ``doc_events`` in hooks.py. Purchase Receipt belongs to
ERPNext, so nothing here edits that app - the logic lives in our module and is
reached by hook.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, formatdate, getdate, today

from food_manufacturing.food_manufacturing_setup.doctype.fm_manufacturing_policy.fm_manufacturing_policy import (
	get_policy_if_any,
)
from food_manufacturing.items import get_item_natures
from food_manufacturing.quality.batch_eligibility import get_row_batches

#: Item natures that must pass incoming inspection before use.
INSPECTED_NATURES = ("Raw Material", "Packaging Material")


def validate(doc, method=None):
	route_to_quarantine(doc)
	validate_supplier_dates(doc)


def on_submit(doc, method=None):
	rows = _receipt_rows(doc.name)
	stamp_batches(doc, rows)
	record_supplier_dates(rows)


def validate_supplier_dates(doc) -> None:
	"""Refuse material the supplier's own date says arrived already expired.

	:func:`record_supplier_dates` only ever moves a batch's dates **earlier**,
	which is the right asymmetry but makes the write one-way: after submit the
	only correction is a deliberate one from ``bench console``. The typo that
	does the damage is therefore a date too far in the *past* - 2016 for 2026 -
	which takes ten years off the shelf life of stock that is fine and leaves
	the batch undispatchable with no way back.

	Its signature is exactly this: a supplier date whose shelf life had already
	run out before the material arrived. Refusing it costs nothing, because the
	date is an optional field - a receipt of genuinely expired material is still
	recorded, by leaving the supplier's date off it or by writing the date the
	plant means to stand behind.

	A date *after* the receipt needs no refusal: dates only move earlier, so
	:func:`record_supplier_dates` already ignores it. See
	``test_a_supplier_date_never_makes_a_batch_look_fresher``.
	"""
	dated = [row for row in doc.get("items") or [] if row.get("fm_supplier_mfg_date")]
	if not dated:
		return

	received = getdate(doc.posting_date or today())
	shelf_life = _shelf_life_days([row.item_code for row in dated])

	for row in dated:
		days = cint(shelf_life.get(row.item_code))
		if not days:
			continue

		made = getdate(row.fm_supplier_mfg_date)
		expiry = getdate(add_days(made, days))
		if expiry >= received:
			continue

		frappe.throw(
			_(
				"Row {0}: the supplier's date says {1} was made on {2}, so its {3} day "
				"shelf life ended on {4} - before it was received on {5}. Correct the "
				"date, or leave it blank to date the batch from the receipt."
			).format(
				row.idx,
				frappe.bold(row.item_code),
				frappe.bold(formatdate(made)),
				days,
				frappe.bold(formatdate(expiry)),
				frappe.bold(formatdate(received)),
			),
			title=_("Material Arrived Expired"),
		)


def route_to_quarantine(doc) -> None:
	"""Send inspected material to the quarantine warehouse.

	Only rows whose Item is classified as raw or packaging material are
	affected, and only when the company's policy requires incoming inspection.
	Unclassified items behave exactly as stock ERPNext, so enabling this app
	does not change existing purchasing.
	"""
	policy = get_policy_if_any(doc.company)
	if not policy or not policy.require_incoming_inspection:
		return

	rows = doc.get("items") or []
	natures = get_item_natures([row.item_code for row in rows])

	redirected = []
	for row in rows:
		if natures.get(row.item_code) not in INSPECTED_NATURES:
			continue

		if row.warehouse == policy.quarantine_warehouse:
			continue

		row.warehouse = policy.quarantine_warehouse
		redirected.append(row.idx)

	if redirected:
		frappe.msgprint(
			_("Rows {0}: material requiring inspection was routed to the quarantine warehouse {1}.").format(
				", ".join(str(idx) for idx in redirected), frappe.bold(policy.quarantine_warehouse)
			),
			indicator="orange",
			alert=True,
		)


def _receipt_rows(receipt: str) -> list:
	"""The receipt's rows, read back from the database.

	ERPNext populates ``serial_and_batch_bundle`` with ``frappe.db.set_value``
	during submit, which does not update the in-memory child rows, so trusting
	``doc.items`` here would miss every bundle-created batch.
	"""
	return frappe.get_all(
		"Purchase Receipt Item",
		filters={"parent": receipt},
		fields=[
			"name",
			"item_code",
			"batch_no",
			"serial_and_batch_bundle",
			"fm_supplier_lot_no",
			"fm_supplier_mfg_date",
		],
		order_by="idx asc",
	)


def stamp_batches(doc, rows: list | None = None) -> None:
	"""Put received batches into Quarantine and record the supplier lot.

	An existing status is never overwritten: a batch may legitimately already be
	released when further quantity of the same batch is received.
	"""
	policy = get_policy_if_any(doc.company)
	if not policy or not policy.require_incoming_inspection:
		return

	rows = _receipt_rows(doc.name) if rows is None else rows
	if not rows:
		return

	natures = get_item_natures([row.item_code for row in rows])
	inspected_rows = [row for row in rows if natures.get(row.item_code) in INSPECTED_NATURES]
	if not inspected_rows:
		return

	batches_by_row = get_row_batches(inspected_rows)
	if not batches_by_row:
		return

	lot_by_row = {row.name: (row.get("fm_supplier_lot_no") or "") for row in inspected_rows}

	all_batches = {b for batches in batches_by_row.values() for b in batches}
	existing = frappe.get_all(
		"Batch",
		filters={"name": ("in", list(all_batches))},
		fields=["name", "fm_quality_status"],
		order_by="name asc",
	)
	status_by_batch = {row.name: row.fm_quality_status for row in existing}

	for row_name, batches in batches_by_row.items():
		for batch_no in batches:
			if status_by_batch.get(batch_no):
				continue

			values = {"fm_quality_status": "Quarantine"}
			if lot_by_row.get(row_name):
				values["fm_supplier_lot_no"] = lot_by_row[row_name]

			frappe.db.set_value("Batch", batch_no, values, update_modified=True)
			frappe.clear_document_cache("Batch", batch_no)


def record_supplier_dates(rows: list) -> None:
	"""Carry the supplier's manufacturing date onto the batch it created.

	ERPNext dates a batch from the receipt, so a lot the supplier blended three
	months before it arrived looks three months fresher than it is - and every
	shelf-life rule in the app inherits that error: remaining-shelf-life at
	dispatch, the near-expiry alert and FEFO all read these two dates.

	The supplier's own date is the one the plant was actually given, so it wins,
	and both dates only ever move **earlier**: receiving a lot may shorten the
	life the batch claims, never extend it. That asymmetry is deliberate - a
	mistyped date should not be able to make expired stock dispatchable.

	Not gated on policy. A date somebody entered is a fact about the material,
	not a rule a company opts into.

	One-way in both senses: the dates only move earlier, and cancelling this
	receipt does not move them back - the batch's original dates are not kept
	anywhere to move back to, and a batch may hold stock from several receipts.
	:func:`validate_supplier_dates` is what stops a typo getting this far; a
	correction after the fact is a deliberate ``frappe.db.set_value`` from
	``bench console``.
	"""
	dated = [row for row in rows if row.get("fm_supplier_mfg_date")]
	if not dated:
		return

	batches_by_row = get_row_batches(dated)
	if not batches_by_row:
		return

	made_by_row = {row.name: getdate(row.fm_supplier_mfg_date) for row in dated}

	batches = {batch for row_batches in batches_by_row.values() for batch in row_batches}
	current = frappe.get_all(
		"Batch",
		filters={"name": ("in", list(batches))},
		fields=["name", "item", "manufacturing_date", "expiry_date"],
		order_by="name asc",
	)
	if not current:
		return

	shelf_life = _shelf_life_days([row.item for row in current])
	current_by_name = {row.name: row for row in current}

	for row_name, row_batches in batches_by_row.items():
		for batch_no in row_batches:
			batch = current_by_name.get(batch_no)
			if not batch:
				continue

			values = _earlier_dates(batch, made_by_row[row_name], shelf_life.get(batch.item))
			if not values:
				continue

			frappe.db.set_value("Batch", batch_no, values, update_modified=True)
			frappe.clear_document_cache("Batch", batch_no)


def _earlier_dates(batch, made, shelf_life_days) -> dict:
	"""Which of the batch's two dates the supplier's date moves earlier."""
	values = {}

	if not batch.manufacturing_date or getdate(batch.manufacturing_date) > made:
		values["manufacturing_date"] = made

	days = cint(shelf_life_days)
	if days:
		expiry = add_days(made, days)
		if not batch.expiry_date or getdate(batch.expiry_date) > getdate(expiry):
			values["expiry_date"] = expiry

	return values


def _shelf_life_days(item_codes) -> dict:
	"""Map item code -> shelf life in days, in one query."""
	codes = {code for code in item_codes if code}
	if not codes:
		return {}

	return {
		row.name: row.shelf_life_in_days
		for row in frappe.get_all(
			"Item",
			filters={"name": ("in", list(codes))},
			fields=["name", "shelf_life_in_days"],
			order_by="name asc",
		)
	}

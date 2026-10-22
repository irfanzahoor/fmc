"""Purchase Receipt extensions: quarantine routing and supplier lot capture.

Registered through ``doc_events`` in hooks.py. Purchase Receipt belongs to
ERPNext, so nothing here edits that app - the logic lives in our module and is
reached by hook.
"""

import frappe
from frappe import _

from food_manufacturing.food_manufacturing_setup.doctype.fm_manufacturing_policy.fm_manufacturing_policy import (
	get_policy_if_any,
)
from food_manufacturing.quality.batch_eligibility import get_row_batches

#: Item natures that must pass incoming inspection before use.
INSPECTED_NATURES = ("Raw Material", "Packaging Material")


def validate(doc, method=None):
	route_to_quarantine(doc)


def on_submit(doc, method=None):
	stamp_batches(doc)


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
	natures = _get_item_natures(rows)

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


def stamp_batches(doc) -> None:
	"""Put received batches into Quarantine and record the supplier lot.

	An existing status is never overwritten: a batch may legitimately already be
	released when further quantity of the same batch is received.
	"""
	policy = get_policy_if_any(doc.company)
	if not policy or not policy.require_incoming_inspection:
		return

	# Read the rows back from the database. ERPNext populates
	# `serial_and_batch_bundle` with frappe.db.set_value during submit, which
	# does not update the in-memory child rows, so trusting `doc.items` here
	# would miss every bundle-created batch.
	rows = frappe.get_all(
		"Purchase Receipt Item",
		filters={"parent": doc.name},
		fields=[
			"name",
			"item_code",
			"batch_no",
			"serial_and_batch_bundle",
			"fm_supplier_lot_no",
		],
		order_by="idx asc",
	)
	if not rows:
		return

	natures = _get_item_natures(rows)
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


def _get_item_natures(rows) -> dict:
	"""Map item code -> fm_material_nature, in one query."""
	item_codes = {row.item_code for row in rows if row.item_code}
	if not item_codes:
		return {}

	items = frappe.get_all(
		"Item",
		filters={"name": ("in", list(item_codes))},
		fields=["name", "fm_material_nature"],
		order_by="name asc",
	)

	return {item.name: item.fm_material_nature for item in items}

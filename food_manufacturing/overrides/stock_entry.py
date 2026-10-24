"""Stock Entry extensions: a manufactured batch starts in Quarantine.

Receiving stamps purchased batches ``Quarantine`` so nothing moves before an
incoming inspection. Production had no equivalent, which left the gate open at
the other end: the batch a Manufacture entry creates for a bulk blend or a
finished pack carried a blank ``fm_quality_status``, and a blank status means
"not quality-managed" to every check in the app. The blend nobody had looked at
was therefore consumable, and the pack nobody had released was dispatchable.

Scope is deliberately the same shape as the receiving stamp: only items the
plant has classified - a Bulk Blend or a Finished Good - and only for a company
whose policy asks for it. An unclassified item behaves exactly as stock ERPNext,
so installing this app does not freeze production that is already running.

Registered through ``doc_events`` in hooks.py; Stock Entry belongs to ERPNext,
so nothing here edits that app.
"""

import frappe
from frappe.utils import cint

from food_manufacturing.food_manufacturing_setup.doctype.fm_manufacturing_policy.fm_manufacturing_policy import (
	get_policy_if_any,
)
from food_manufacturing.items import get_item_natures
from food_manufacturing.quality.batch_eligibility import get_row_batches

#: Entries that bring a new batch of our own making into stock.
PRODUCTION_PURPOSES = ("Manufacture", "Repack")

#: Natures whose batches the plant manages through quality decisions.
MANAGED_NATURES = ("Bulk Blend", "Finished Good")


def on_submit(doc, method=None):
	stamp_production_batches(doc)


def stamp_production_batches(doc) -> None:
	"""Put the batches this entry produced into Quarantine.

	An existing status is never overwritten: a second run may legitimately top
	up a batch that quality has already released.
	"""
	if doc.purpose not in PRODUCTION_PURPOSES:
		return

	policy = get_policy_if_any(doc.company)
	if not policy or not cint(policy.quarantine_production_output):
		return

	rows = _output_rows(doc.name)
	if not rows:
		return

	natures = get_item_natures([row.item_code for row in rows])
	managed = [row for row in rows if natures.get(row.item_code) in MANAGED_NATURES]
	if not managed:
		return

	batches_by_row = get_row_batches(managed)
	if not batches_by_row:
		return

	batches = {batch for row_batches in batches_by_row.values() for batch in row_batches}
	stamped = frappe.get_all(
		"Batch",
		filters={"name": ("in", list(batches))},
		fields=["name", "fm_quality_status"],
		order_by="name asc",
	)

	for row in stamped:
		if row.fm_quality_status:
			continue

		frappe.db.set_value("Batch", row.name, {"fm_quality_status": "Quarantine"}, update_modified=True)
		frappe.clear_document_cache("Batch", row.name)


def _output_rows(stock_entry: str) -> list:
	"""Rows that put stock in rather than take it out.

	Read back from the database because ERPNext assigns
	``serial_and_batch_bundle`` with ``frappe.db.set_value`` during submit, which
	leaves the in-memory child rows stale - trusting ``doc.items`` here would
	miss every batch ERPNext allocated itself.
	"""
	rows = frappe.get_all(
		"Stock Entry Detail",
		filters={"parent": stock_entry},
		fields=[
			"name",
			"item_code",
			"s_warehouse",
			"t_warehouse",
			"batch_no",
			"serial_and_batch_bundle",
		],
		order_by="idx asc",
	)

	return [row for row in rows if row.t_warehouse and not row.s_warehouse]

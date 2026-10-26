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


def before_cancel(doc, method=None):
	release_production_batches(doc)


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

	batches = _managed_batches(doc)
	if not batches:
		return

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


def release_production_batches(doc) -> None:
	"""Undo the Quarantine this entry stamped.

	A cancelled run produced nothing, so leaving its batches in the release
	queue asks quality to decide about stock that no longer exists.

	Two things are deliberately left alone. A batch quality has already ruled on
	keeps that ruling: an FM Batch Release is a record of somebody deciding, and
	a cancellation is not the place to overturn it. And a batch whose status is
	anything other than ``Quarantine`` was not left that way by this stamp.

	Not gated on policy either, unlike the stamp. The policy may have been
	switched off since the entry was submitted, and the stamp still needs
	undoing - a rule that only runs while it is enabled cannot clean up after
	itself.

	Hooked on ``before_cancel`` rather than ``on_cancel`` because ERPNext clears
	``batch_no`` and ``serial_and_batch_bundle`` on the rows as part of
	cancelling, so by ``on_cancel`` there is nothing left to say which batches
	this entry produced. Both run inside the cancel's own transaction, so a
	cancel that then fails takes this write back with it.
	"""
	batches = _managed_batches(doc)
	if not batches:
		return

	quarantined = frappe.get_all(
		"Batch",
		filters={"name": ("in", list(batches)), "fm_quality_status": "Quarantine"},
		pluck="name",
		order_by="name asc",
	)
	if not quarantined:
		return

	decided = set(
		frappe.get_all(
			"FM Batch Release",
			filters={"batch": ("in", quarantined), "docstatus": 1},
			pluck="batch",
			order_by="batch asc",
		)
	)

	for batch_no in quarantined:
		if batch_no in decided:
			continue

		frappe.db.set_value("Batch", batch_no, {"fm_quality_status": None}, update_modified=True)
		frappe.clear_document_cache("Batch", batch_no)


def _managed_batches(doc) -> set:
	"""Batches this entry produced of items the plant manages by quality.

	One definition for the stamp and the un-stamp, so the two cannot disagree
	about which batches are in scope.
	"""
	if doc.purpose not in PRODUCTION_PURPOSES:
		return set()

	rows = _output_rows(doc.name)
	if not rows:
		return set()

	natures = get_item_natures([row.item_code for row in rows])
	managed = [row for row in rows if natures.get(row.item_code) in MANAGED_NATURES]
	if not managed:
		return set()

	batches_by_row = get_row_batches(managed)

	return {batch for row_batches in batches_by_row.values() for batch in row_batches}


def _output_rows(stock_entry: str) -> list:
	"""Rows carrying what this entry made.

	``is_finished_item`` is the flag ERPNext sets on the row holding the
	production item, so it is read rather than inferred. The shape of the
	warehouses was the first guess here and it is only a heuristic: a scrap row
	also carries nothing but a target warehouse, so it quarantined scrap nobody
	would ever release.

	It stays as the fallback for the one case ERPNext leaves the flag unset -
	``mark_finished_and_secondary_items`` returns early on an independent
	Manufacture entry naming neither a Work Order nor a BOM, because there it
	cannot tell either. Quarantining a little too much is the safe side of that
	guess; quarantining nothing is not.

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
			"is_finished_item",
		],
		order_by="idx asc",
	)

	if finished := [row for row in rows if row.is_finished_item and row.t_warehouse]:
		return finished

	return [row for row in rows if row.t_warehouse and not row.s_warehouse]

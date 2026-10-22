"""QC release queue API.

The decision itself goes through ``FM Batch Release``, so the transition table,
the inspection requirement, the row lock against concurrent releases and the
audit trail all apply identically whether the decision is made here or in the
Desk. This module adds no rules of its own.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

from food_manufacturing.dispatch.shelf_life import get_batch_shelf_life, remaining_shelf_life_percent
from food_manufacturing.production.genealogy import trace_backward
from food_manufacturing.stock_levels import get_batch_quantities

PENDING_STATUSES = ("Quarantine", "Hold")


@frappe.whitelist()
def get_release_queue(company: str, status: str | None = None, limit: int = 100) -> list:
	"""Batches awaiting a quality decision, oldest first."""
	frappe.has_permission("Batch", "read", throw=True)
	frappe.has_permission("FM Batch Release", "read", throw=True)

	filters = {"disabled": 0}
	filters["fm_quality_status"] = status if status in PENDING_STATUSES else ("in", list(PENDING_STATUSES))

	batches = frappe.get_list(
		"Batch",
		filters=filters,
		fields=[
			"name",
			"item",
			"item_name",
			"fm_quality_status",
			"fm_supplier_lot_no",
			"supplier",
			"expiry_date",
			"manufacturing_date",
			"creation",
		],
		order_by="creation asc",
		limit=cint(limit) or 100,
	)
	if not batches:
		return []

	warehouses = frappe.get_all(
		"Warehouse", filters={"company": company}, pluck="name", order_by="name asc"
	)
	if not warehouses:
		return []

	names = [batch["name"] for batch in batches]
	quantities = get_batch_quantities(names, warehouses)
	shelf_life = get_batch_shelf_life(names)

	queue = []
	for batch in batches:
		qty = flt(quantities.get(batch["name"]))
		# A pending batch with no stock in this company needs no decision.
		if qty <= 0:
			continue

		batch["qty"] = qty
		batch["remaining_shelf_life_percent"] = remaining_shelf_life_percent(
			shelf_life.get(batch["name"]) or {}
		)
		queue.append(batch)

	return queue


@frappe.whitelist()
def get_batch_context(batch: str) -> dict:
	"""Everything a quality manager needs before deciding on one batch."""
	frappe.has_permission("Batch", "read", doc=batch, throw=True)

	doc = frappe.get_doc("Batch", batch)
	doc.check_permission("read")

	inspections = frappe.get_list(
		"Quality Inspection",
		filters={"item_code": doc.item, "docstatus": 1},
		fields=["name", "status", "inspection_type", "report_date"],
		order_by="report_date desc",
		limit=10,
	)

	history = frappe.get_list(
		"FM Batch Release",
		filters={"batch": batch, "docstatus": 1},
		fields=["name", "decision", "reason", "decided_by", "posting_datetime", "previous_status"],
		order_by="posting_datetime desc",
		limit=20,
	)

	detail = get_batch_shelf_life([batch]).get(batch) or {}

	return {
		"batch": {
			"name": doc.name,
			"item": doc.item,
			"item_name": doc.item_name,
			"quality_status": doc.get("fm_quality_status"),
			"supplier_lot_no": doc.get("fm_supplier_lot_no"),
			"supplier": doc.supplier,
			"expiry_date": doc.expiry_date,
			"manufacturing_date": doc.manufacturing_date,
			"remaining_shelf_life_percent": remaining_shelf_life_percent(detail),
		},
		"inspections": inspections,
		"history": history,
		# Where this batch came from, so a decision is informed.
		"genealogy": trace_backward(doc.item, doc.name, max_depth=3),
	}


@frappe.whitelist(methods=["POST"])
def record_decision(
	batch: str,
	company: str,
	decision: str,
	reason: str | None = None,
	quality_inspection: str | None = None,
	evidence: str | None = None,
) -> dict:
	"""Create and submit an FM Batch Release.

	Permission to decide is the permission to create that document, which only
	FM Quality Manager and System Manager hold - so an inspector calling this
	endpoint directly is refused by the framework, not by a check here.
	"""
	frappe.has_permission("FM Batch Release", "create", throw=True)

	if decision not in ("Release", "Hold", "Reject"):
		frappe.throw(_("Unknown decision {0}.").format(frappe.bold(decision)))

	release = frappe.get_doc(
		{
			"doctype": "FM Batch Release",
			"batch": batch,
			"company": company,
			"decision": decision,
			"reason": reason,
			"quality_inspection": quality_inspection,
			"evidence": evidence,
		}
	)
	release.insert()
	release.submit()

	return {
		"name": release.name,
		"batch": batch,
		"previous_status": release.previous_status,
		"quality_status": frappe.db.get_value("Batch", batch, "fm_quality_status"),
	}


@frappe.whitelist()
def get_queue_counts(company: str) -> dict:
	"""Badge counts for the console header."""
	frappe.has_permission("Batch", "read", throw=True)

	queue = get_release_queue(company)
	return {
		"quarantine": sum(1 for b in queue if b["fm_quality_status"] == "Quarantine"),
		"hold": sum(1 for b in queue if b["fm_quality_status"] == "Hold"),
		"total": len(queue),
	}

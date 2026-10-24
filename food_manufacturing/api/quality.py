"""QC release queue API.

The decision itself goes through ``FM Batch Release``, so the transition table,
the inspection requirement, the row lock against concurrent releases and the
audit trail all apply identically whether the decision is made here or in the
Desk. This module adds no rules of its own.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

from food_manufacturing.items import get_item_uoms
from food_manufacturing.dispatch.shelf_life import get_batch_shelf_life, remaining_shelf_life_percent
from food_manufacturing.quality.inspection import get_inspections
from food_manufacturing.production.genealogy import trace_backward
from food_manufacturing.stock_levels import get_batch_quantities

PENDING_STATUSES = ("Quarantine", "Hold")

#: Every status the queue can be filtered to. Pending by default, because that
#: is what needs doing; the decided ones are for looking back.
QUEUE_STATUSES = ("Quarantine", "Hold", "Released", "Rejected")


@frappe.whitelist()
def get_release_queue(
	company: str,
	status: str | None = None,
	search: str | None = None,
	limit: int = 100,
	start: int = 0,
) -> list:
	"""Batches awaiting a quality decision, oldest first."""
	frappe.has_permission("Batch", "read", throw=True)
	frappe.has_permission("Company", "read", doc=company, throw=True)
	frappe.has_permission("FM Batch Release", "read", throw=True)

	filters = {"disabled": 0}
	if status in QUEUE_STATUSES:
		filters["fm_quality_status"] = status
	else:
		filters["fm_quality_status"] = ("in", list(PENDING_STATUSES))

	# Searched in the query rather than in the browser: a site with thousands of
	# batches should not ship them all so the client can hide most.
	or_filters = None
	if search:
		term = f"%{search.strip()[:64]}%"
		or_filters = {
			"name": ("like", term),
			"item": ("like", term),
			"item_name": ("like", term),
			"fm_supplier_lot_no": ("like", term),
		}

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
		# Pending reads oldest-first (longest waiting); a decided list reads
		# newest-first, because that is a log you look back through.
		or_filters=or_filters,
		order_by="modified desc" if status in ("Released", "Rejected") else "creation asc, name asc",
		limit_page_length=0,
	)
	if not batches:
		return []

	warehouses = frappe.get_all("Warehouse", filters={"company": company}, pluck="name", order_by="name asc")
	if not warehouses:
		return []

	names = [batch["name"] for batch in batches]
	quantities = get_batch_quantities(names, warehouses)
	shelf_life = get_batch_shelf_life(names)
	# A quantity without its unit is not a quantity: 450 of chilli could be
	# kilograms or pouches, and the queue is read to decide what to do with it.
	uoms = get_item_uoms(batch["item"] for batch in batches)

	queue = []
	for batch in batches:
		qty = flt(quantities.get(batch["name"]))
		# A pending batch with no stock in this company needs no decision.
		if qty <= 0:
			continue

		batch["qty"] = qty
		batch["stock_uom"] = uoms.get(batch["item"])
		batch["remaining_shelf_life_percent"] = remaining_shelf_life_percent(
			shelf_life.get(batch["name"]) or {}
		)
		queue.append(batch)

	# Apply pagination after company stock filtering.
	page_size = min(max(cint(limit), 1), 500) if cint(limit) else len(queue)
	start = max(cint(start), 0)
	return queue[start : start + page_size]


@frappe.whitelist(methods=["POST"])
def raise_inspection(
	batch: str,
	stage: str,
	reference_type: str,
	reference_name: str,
	sample_size: float,
	readings: list | str | None = None,
	remarks: str | None = None,
	status: str | None = None,
	submit: int = 0,
) -> dict:
	"""Raise a Quality Inspection for a batch at an incoming, in-process or
	finished-product check. Limits come from the item's template."""
	from food_manufacturing.quality.inspection import create_inspection

	readings = frappe.parse_json(readings) if isinstance(readings, str) else readings

	return create_inspection(
		batch,
		stage,
		reference_type,
		reference_name,
		sample_size,
		readings=readings,
		remarks=remarks,
		status=status,
		submit=bool(cint(submit)),
	)


@frappe.whitelist()
def get_inspection_readings(inspection: str) -> list:
	"""Measured values of one inspection, with the limits they were read against."""
	from food_manufacturing.quality.inspection import get_readings

	return get_readings(inspection)


@frappe.whitelist()
def get_batch_context(batch: str) -> dict:
	"""Everything a quality manager needs before deciding on one batch."""
	frappe.has_permission("Batch", "read", doc=batch, throw=True)

	doc = frappe.get_doc("Batch", batch)
	doc.check_permission("read")

	# Every inspection, not only the accepted ones: a rejection is the single
	# most relevant fact before a decision, and filtering it out made the
	# history a record of good news.
	inspections = get_inspections(batch, limit=10)

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


@frappe.whitelist()
def get_batch_trail(batch: str, company: str) -> dict:
	"""Where this batch came from and where it went, as real documents.

	Built from the existing genealogy and recall engines rather than a new
	query, so the trail a quality manager reads is the same one a recall
	investigation produces. Every row names a document the reader can open.
	"""
	frappe.has_permission("Batch", "read", doc=batch, throw=True)
	frappe.has_permission("Company", "read", doc=company, throw=True)

	item = frappe.db.get_value("Batch", batch, "item")
	if not item:
		frappe.throw(_("Batch {0} does not exist.").format(frappe.bold(batch)))

	return {
		"consumed": _consumed_into(item, batch),
		"produced_by": _produced_by(item, batch),
		"delivered": _delivered(batch, company),
	}


def _produced_by(item: str, batch: str) -> list:
	"""The run that made this batch, if it was made rather than bought."""
	from food_manufacturing.production.genealogy import get_producing_work_orders

	try:
		orders = get_producing_work_orders(item, batch)
	except frappe.PermissionError:
		return []

	return [{"doctype": "Work Order", "name": name} for name in orders]


def _consumed_into(item: str, batch: str) -> list:
	"""The lots this batch was made from, one level back.

	One level, not the whole tree: a quality manager asks "what went into this",
	and `FM Recall Investigation` is where a full trace belongs.
	"""
	from food_manufacturing.production.genealogy import trace_backward

	try:
		tree = trace_backward(item, batch, max_depth=2)
	except frappe.PermissionError:
		return []

	return [
		{
			"doctype": "Batch",
			"name": node.get("batch_no"),
			"item_code": node.get("item_code"),
			"supplier_lot": node.get("supplier_lot"),
		}
		for node in (tree.get("inputs") or [])
		if node.get("batch_no")
	]


def _delivered(batch: str, company: str) -> list:
	"""Customer deliveries this batch reached."""
	from food_manufacturing.api.recall import get_recall

	try:
		result = get_recall(batch, company)
	except frappe.PermissionError:
		return []

	return [
		{
			"doctype": "Delivery Note",
			"name": row["delivery_note"],
			"customer": row.get("customer"),
			"posting_date": str(row.get("posting_date")) if row.get("posting_date") else None,
			"qty": flt(row.get("stock_qty")),
			"uom": row.get("stock_uom"),
			"is_return": bool(row.get("is_return")),
		}
		for row in (result.get("deliveries") or [])
		if row.get("batch_no") == batch
	]


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

	queue = get_release_queue(company, limit=0)
	return {
		"quarantine": sum(1 for b in queue if b["fm_quality_status"] == "Quarantine"),
		"hold": sum(1 for b in queue if b["fm_quality_status"] == "Hold"),
		"total": len(queue),
	}

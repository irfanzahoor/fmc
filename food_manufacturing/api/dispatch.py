"""Dispatch and FEFO picking API.

The picklist is a *recommendation*; the rules that actually bind are the ones in
``dispatch/shelf_life.py`` and ``dispatch/fefo.py``, which run on the Delivery
Note itself. So a client that ignores the recommendation still cannot ship
expired, held or rejected stock.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

from food_manufacturing.api.idempotency import retry_safe

from food_manufacturing.dispatch.fefo import get_fefo_batches, get_fefo_batches_bulk
from food_manufacturing.dispatch.shelf_life import get_batch_shelf_life, remaining_shelf_life_percent
from food_manufacturing.food_manufacturing_setup.doctype.fm_manufacturing_policy.fm_manufacturing_policy import (
	get_policy_if_any,
)


@frappe.whitelist()
def get_open_sales_orders(company: str, limit: int = 50) -> list:
	"""Submitted Sales Orders with quantity still to deliver."""
	frappe.has_permission("Sales Order", "read", throw=True)

	return frappe.get_list(
		"Sales Order",
		filters={
			"company": company,
			"docstatus": 1,
			"status": ("not in", ("Closed", "Completed")),
			"per_delivered": ("<", 100),
		},
		fields=[
			"name",
			"customer",
			"customer_name",
			"transaction_date",
			"delivery_date",
			"per_delivered",
		],
		order_by="delivery_date asc, name asc",
		limit=cint(limit) or 50,
	)


@frappe.whitelist()
def get_picklist(sales_order: str) -> dict:
	"""Outstanding lines of a Sales Order with a FEFO suggestion for each."""
	frappe.has_permission("Sales Order", "read", doc=sales_order, throw=True)

	doc = frappe.get_doc("Sales Order", sales_order)
	doc.check_permission("read")

	policy = get_policy_if_any(doc.company)

	available = get_fefo_batches_bulk([(row.item_code, row.warehouse) for row in doc.items], doc.company)
	all_candidates = [batch for batches in available.values() for batch in batches]
	details = get_batch_shelf_life([batch["batch_no"] for batch in all_candidates])
	lines = []
	for row in doc.items:
		pending = flt(row.qty) - flt(row.delivered_qty)
		if pending <= 0:
			continue

		factor = flt(row.conversion_factor) or 1
		candidates = _annotate(available.get((row.item_code, row.warehouse), []), policy, details)
		# The UI and allocation API use stock UOM; ERPNext rows retain their sales UOM.
		suggestion, shortfall = _allocate(
			[b for b in candidates if not b["blocked_reason"]], pending * factor
		)
		for pick in suggestion:
			for candidate in available.get((row.item_code, row.warehouse), []):
				if candidate["batch_no"] == pick["batch_no"]:
					candidate["available_qty"] -= pick["qty"]
		# Shared candidate dictionaries reserve suggestions across repeated order lines.

		lines.append(
			{
				"name": row.name,
				"idx": row.idx,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"uom": row.uom,
				"stock_uom": row.stock_uom,
				"rate": flt(row.rate),
				"ordered_qty": flt(row.qty),
				"delivered_qty": flt(row.delivered_qty),
				"pending_qty": pending,
				"warehouse": row.warehouse,
				"suggestion": suggestion,
				"shortfall": shortfall,
				"candidates": candidates,
				"conversion_factor": factor,
			}
		)

	return {
		"sales_order": sales_order,
		"customer": doc.customer,
		"customer_name": doc.customer_name,
		"company": doc.company,
		"fefo_mode": (policy.enforce_fefo if policy else "Off"),
		"min_remaining_shelf_life_percent": flt(policy.min_remaining_shelf_life_percent) if policy else 0.0,
		"lines": lines,
	}


@frappe.whitelist(methods=["POST"])
@retry_safe("Sales Order", "sales_order", "Delivery Note", "delivery_note")
def create_delivery_note(sales_order: str, lines, request_id: str | None = None) -> dict:
	"""Create and submit a Delivery Note for the chosen batches.

	``lines`` is ``[{name, allocations: [{batch_no, qty}]}]`` where ``name`` is
	the Sales Order Item row. One Delivery Note row is produced per allocation,
	which is how a split pick is expressed.
	"""
	from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

	frappe.has_permission("Sales Order", "read", doc=sales_order, throw=True)
	frappe.has_permission("Delivery Note", "create", throw=True)

	lines = frappe.parse_json(lines) if isinstance(lines, str) else lines
	if not lines:
		frappe.throw(_("Nothing to dispatch."))

	allocations = {}
	for line in lines:
		picks = [p for p in (line.get("allocations") or []) if flt(p.get("qty")) > 0]
		if picks:
			allocations[line.get("name")] = picks

	if not allocations:
		frappe.throw(_("Allocate a batch and quantity for at least one line."))

	note = frappe.get_doc(make_delivery_note(sales_order))

	rows = []
	for row in note.items:
		picks = allocations.get(row.so_detail)
		if not picks:
			continue

		for pick in picks:
			clone = frappe.copy_doc(row, ignore_no_copy=False)
			clone.qty = flt(pick["qty"]) / (flt(row.conversion_factor) or 1)
			clone.stock_qty = flt(pick["qty"])
			clone.use_serial_batch_fields = 1
			clone.batch_no = pick["batch_no"]
			rows.append(clone)

	if not rows:
		frappe.throw(_("None of the given lines belong to {0}.").format(frappe.bold(sales_order)))

	note.set("items", rows)
	note.insert()
	note.submit()

	return {"delivery_note": note.name}


def _allocate(candidates: list, wanted: float):
	"""Split ``wanted`` across ``candidates`` in the order given."""
	remaining = flt(wanted)
	picks = []

	for batch in candidates:
		if remaining <= 0:
			break

		take = min(flt(batch["available_qty"]), remaining)
		if take <= 0:
			continue

		picks.append({"batch_no": batch["batch_no"], "qty": flt(take)})
		remaining -= take

	return picks, flt(remaining) if remaining > 0 else 0.0


def _annotate(candidates: list, policy, details=None) -> list:
	"""Add the shelf-life figure and whether each batch would be refused."""
	if not candidates:
		return []

	details = details if details is not None else get_batch_shelf_life([b["batch_no"] for b in candidates])
	minimum = flt(policy.min_remaining_shelf_life_percent) if policy else 0.0

	annotated = []
	for batch in candidates:
		detail = details.get(batch["batch_no"]) or {}
		remaining = remaining_shelf_life_percent(detail)

		blocked_reason = None
		if remaining is not None and minimum > 0 and remaining < minimum:
			blocked_reason = _("Below the {0}% shelf life required for dispatch.").format(flt(minimum, 2))

		annotated.append(
			{
				**batch,
				"remaining_shelf_life_percent": remaining,
				"blocked_reason": blocked_reason,
			}
		)

	return annotated

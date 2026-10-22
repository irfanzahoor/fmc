"""Operator production console API.

Every endpoint is whitelisted, checks permission explicitly, and mutations are
POST-only. The screen is a convenience over the same server rules the Desk uses:
nothing here bypasses the batch quality gate, the recipe approval guard or the
stock validations, because all of those live in doc_events and run whichever
path creates the document.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

from food_manufacturing.dispatch.fefo import get_fefo_batches
from food_manufacturing.production.genealogy import get_consumed_lots

#: Work Order states an operator still has something to do about.
OPEN_STATUSES = ("Not Started", "In Process", "Submitted")


@frappe.whitelist()
def get_production_queue(company: str, status: str | None = None, limit: int = 50) -> list:
	"""Work Orders awaiting or undergoing production.

	Uses ``get_list`` so the caller's User Permissions apply - a user restricted
	to one company cannot read another's queue through this endpoint.
	"""
	frappe.has_permission("Work Order", "read", throw=True)

	filters = {"company": company, "docstatus": 1}
	filters["status"] = status if status else ("in", list(OPEN_STATUSES))

	rows = frappe.get_list(
		"Work Order",
		filters=filters,
		fields=[
			"name",
			"production_item",
			"item_name",
			"bom_no",
			"qty",
			"produced_qty",
			"process_loss_qty",
			"status",
			"stock_uom",
			"fg_warehouse",
			"wip_warehouse",
			"planned_start_date",
			"fm_actual_yield_percent",
			"fm_yield_variance_percent",
			"fm_yield_flagged",
			"fm_yield_basis",
		],
		order_by="planned_start_date asc, creation asc",
		limit=cint(limit) or 50,
	)

	for row in rows:
		row["pending_qty"] = flt(row["qty"]) - flt(row["produced_qty"]) - flt(row["process_loss_qty"])

	return rows


@frappe.whitelist()
def get_work_order_detail(work_order: str) -> dict:
	"""Everything the console needs for one run, in one round trip."""
	frappe.has_permission("Work Order", "read", doc=work_order, throw=True)

	doc = frappe.get_doc("Work Order", work_order)
	doc.check_permission("read")

	ingredients = []
	for row in doc.get("required_items") or []:
		ingredients.append(
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"required_qty": flt(row.required_qty),
				"transferred_qty": flt(row.transferred_qty),
				"consumed_qty": flt(row.consumed_qty),
				"stock_uom": row.stock_uom,
				"source_warehouse": row.source_warehouse or doc.wip_warehouse,
				# Released lots only, in FEFO order, so the operator picks the
				# right one without having to know the rule.
				"available_lots": get_fefo_batches(
					row.item_code,
					row.source_warehouse or doc.wip_warehouse,
					doc.company,
				),
			}
		)

	return {
		"work_order": {
			"name": doc.name,
			"production_item": doc.production_item,
			"item_name": doc.item_name,
			"bom_no": doc.bom_no,
			"qty": flt(doc.qty),
			"produced_qty": flt(doc.produced_qty),
			"process_loss_qty": flt(doc.process_loss_qty),
			"status": doc.status,
			"stock_uom": doc.stock_uom,
			"company": doc.company,
			"fg_warehouse": doc.fg_warehouse,
			"wip_warehouse": doc.wip_warehouse,
			"skip_transfer": cint(doc.skip_transfer),
			"yield_percent": flt(doc.get("fm_actual_yield_percent")),
			"yield_variance_percent": flt(doc.get("fm_yield_variance_percent")),
			"yield_flagged": cint(doc.get("fm_yield_flagged")),
			"yield_basis": doc.get("fm_yield_basis"),
		},
		"ingredients": ingredients,
		"consumed_lots": get_consumed_lots(doc.name),
	}


@frappe.whitelist(methods=["POST"])
def finish_production_run(
	work_order: str,
	qty: float,
	finished_batch: str | None = None,
	process_loss_qty: float = 0,
) -> dict:
	"""Post the Manufacture Stock Entry for a run.

	Deliberately thin: it builds ERPNext's own Manufacture entry via
	``make_stock_entry`` and submits it, so valuation, the batch quality gate and
	every stock validation behave exactly as they do in the Desk. Returns the
	entry name and the refreshed yield.
	"""
	from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

	frappe.has_permission("Work Order", "write", doc=work_order, throw=True)
	frappe.has_permission("Stock Entry", "create", throw=True)

	qty = flt(qty)
	if qty <= 0:
		frappe.throw(_("Quantity to finish must be greater than zero."))

	order = frappe.get_doc("Work Order", work_order)
	order.check_permission("write")

	if order.docstatus != 1:
		frappe.throw(_("Work Order {0} is not submitted.").format(frappe.bold(work_order)))

	process_loss_qty = flt(process_loss_qty)
	if process_loss_qty < 0:
		frappe.throw(_("Process loss cannot be negative."))

	remaining = flt(order.qty) - flt(order.produced_qty) - flt(order.process_loss_qty)
	if qty + process_loss_qty > remaining + 0.0001:
		frappe.throw(
			_("Only {0} {1} is left to finish on this Work Order.").format(
				flt(remaining), order.stock_uom
			),
			title=_("Quantity Exceeds the Work Order"),
		)

	entry = frappe.get_doc(make_stock_entry(work_order, "Manufacture", qty + process_loss_qty))

	for row in entry.items:
		if row.item_code == order.production_item and row.t_warehouse:
			row.qty = qty
			row.transfer_qty = qty
			if finished_batch:
				row.use_serial_batch_fields = 1
				row.batch_no = finished_batch

	if process_loss_qty:
		entry.process_loss_qty = process_loss_qty

	entry.insert()
	entry.submit()

	order.reload()
	return {
		"stock_entry": entry.name,
		"produced_qty": flt(order.produced_qty),
		"process_loss_qty": flt(order.process_loss_qty),
		"yield_percent": flt(order.get("fm_actual_yield_percent")),
		"yield_flagged": cint(order.get("fm_yield_flagged")),
		"yield_basis": order.get("fm_yield_basis"),
	}

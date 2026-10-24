"""Operator production console API.

Every endpoint is whitelisted, checks permission explicitly, and mutations are
POST-only. The screen is a convenience over the same server rules the Desk uses:
nothing here bypasses the batch quality gate, the recipe approval guard or the
stock validations, because all of those live in doc_events and run whichever
path creates the document.
"""

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import cint, flt

from food_manufacturing.api.idempotency import retry_safe

from food_manufacturing.dispatch.fefo import get_fefo_batches_bulk
from food_manufacturing.production.genealogy import get_consumed_lots

#: Work Order states an operator still has something to do about.
OPEN_STATUSES = ("Not Started", "In Process", "Submitted")


@frappe.whitelist()
def get_production_queue(
	company: str,
	status: str | None = None,
	search: str | None = None,
	limit: int = 50,
	start: int = 0,
) -> list:
	"""Work Orders awaiting or undergoing production.

	Uses ``get_list`` so the caller's User Permissions apply - a user restricted
	to one company cannot read another's queue through this endpoint.

	Searching and paging happen **in the query**, not in the browser: a plant
	with two thousand open runs should not ship two thousand rows so the client
	can hide most of them.
	"""
	frappe.has_permission("Work Order", "read", throw=True)

	filters = {"company": company, "docstatus": 1}
	filters["status"] = status if status in OPEN_STATUSES else ("in", list(OPEN_STATUSES))

	or_filters = None
	if search:
		# A run is looked up by its number or by what it makes, which is what an
		# operator has in front of them.
		term = f"%{search.strip()[:64]}%"
		or_filters = {"name": ("like", term), "item_name": ("like", term),
		              "production_item": ("like", term)}

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
		or_filters=or_filters,
		order_by="planned_start_date asc, creation asc",
		limit=min(max(cint(limit) or 50, 1), 200),
		start=max(cint(start), 0),
	)

	uoms = _production_item_uoms([row["production_item"] for row in rows])
	shortages = _shortage_counts(company, [row["name"] for row in rows])

	for row in rows:
		row["pending_qty"] = flt(row["qty"]) - flt(row["produced_qty"]) - flt(row["process_loss_qty"])
		row["stock_uom"] = uoms.get(row["production_item"], row["stock_uom"])
		row["short_items"] = shortages.get(row["name"], 0)
		row["material_ready"] = row["short_items"] == 0

	return rows


def _shortage_counts(company: str, work_orders: list) -> dict:
	"""How many ingredients each run is short of, from the shared engine.

	Reuses ``api/exceptions`` rather than re-deriving availability: two answers
	to "is this run short" is one too many.
	"""
	if not work_orders:
		return {}

	from food_manufacturing.api.exceptions import get_exceptions

	try:
		short = get_exceptions(company)["material_short"]
	except frappe.PermissionError:
		return {}

	wanted = set(work_orders)
	return {
		row["work_order"]: len(row["items"])
		for row in short
		if row["work_order"] in wanted
	}


def _available_quantities(company: str, pairs: set) -> dict:
	"""On-hand quantity per (item, warehouse), in one query."""
	items = {item for item, _warehouse in pairs if item}
	warehouses = {warehouse for _item, warehouse in pairs if warehouse}
	if not items or not warehouses:
		return {}

	owned = set(
		frappe.get_all(
			"Warehouse",
			filters={"company": company, "name": ("in", list(warehouses))},
			pluck="name",
		)
	)
	if not owned:
		return {}

	bin_table = frappe.qb.DocType("Bin")
	rows = (
		frappe.qb.from_(bin_table)
		.select(bin_table.item_code, bin_table.warehouse, Sum(bin_table.actual_qty).as_("qty"))
		.where(bin_table.item_code.isin(list(items)))
		.where(bin_table.warehouse.isin(list(owned)))
		.groupby(bin_table.item_code, bin_table.warehouse)
	).run(as_dict=True)

	return {(row.item_code, row.warehouse): flt(row.qty) for row in rows}


def _next_action(doc, ingredients: list) -> dict:
	"""What this run needs next, and whether it can be done yet.

	The console shows one primary action per stage rather than every button at
	once. ``enabled`` false still renders the action, with the reason - hiding
	it would leave an operator wondering where it went.
	"""
	short = [row for row in ingredients if flt(row.get("short_qty")) > 0]
	remaining = flt(doc.qty) - flt(doc.produced_qty) - flt(doc.process_loss_qty)

	if remaining <= 0:
		return {"action": "none", "label": "Run complete", "enabled": False,
		        "reason": _("Everything planned has been produced.")}

	if short:
		names = ", ".join(row["item_name"] or row["item_code"] for row in short[:3])
		return {
			"action": "complete",
			"label": "Complete run",
			"enabled": False,
			"reason": _("Short of {0}. Receive or transfer stock first.").format(names),
		}

	return {"action": "complete", "label": "Complete run", "enabled": True, "reason": None}


def _production_item_uoms(item_codes: list) -> dict:
	"""Stock UOM per produced item, read from the Item.

	``Work Order.stock_uom`` is only fetched by the Desk form, so a Work Order
	created through the API or an import keeps the field default of ``Nos`` -
	a blend planned in kilograms then reads "500 Nos" everywhere. The Item is
	the authority, so it is asked, once for the whole page rather than per row.
	"""
	codes = {code for code in item_codes if code}
	if not codes:
		return {}

	rows = frappe.get_all(
		"Item",
		filters={"name": ("in", list(codes))},
		fields=["name", "stock_uom"],
	)
	return {row.name: row.stock_uom for row in rows}


@frappe.whitelist()
def get_work_order_detail(work_order: str) -> dict:
	"""Everything the console needs for one run, in one round trip."""
	frappe.has_permission("Work Order", "read", doc=work_order, throw=True)

	doc = frappe.get_doc("Work Order", work_order)
	doc.check_permission("read")

	lots = get_fefo_batches_bulk(
		[(row.item_code, row.source_warehouse or doc.wip_warehouse) for row in doc.required_items],
		doc.company,
	)
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
				# What the run still needs, and whether it is there. The lots
				# below say which batches are eligible; this says whether there
				# are enough of them.
				"outstanding_qty": max(
					flt(row.required_qty) - flt(row.transferred_qty) - flt(row.consumed_qty), 0.0
				),
				# Released lots only, in FEFO order, so the operator picks the
				# right one without having to know the rule.
				"available_lots": lots.get((row.item_code, row.source_warehouse or doc.wip_warehouse), []),
			}
		)

	available = _available_quantities(
		doc.company,
		{
			(row["item_code"], row["source_warehouse"])
			for row in ingredients
			if row["outstanding_qty"] > 0
		},
	)
	for row in ingredients:
		row["available_qty"] = available.get((row["item_code"], row["source_warehouse"]))
		row["short_qty"] = (
			max(row["outstanding_qty"] - flt(row["available_qty"]), 0.0)
			if row["available_qty"] is not None
			else None
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
			"stock_uom": _production_item_uoms([doc.production_item]).get(
				doc.production_item, doc.stock_uom
			),
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
		"material_ready": not any(flt(row.get("short_qty")) > 0 for row in ingredients),
		# The one thing to do next, decided on the server so the button and the
		# rule that governs it cannot disagree.
		"next_action": _next_action(doc, ingredients),
		"consumed_lots": get_consumed_lots(doc.name),
	}


@frappe.whitelist(methods=["POST"])
@retry_safe("Work Order", "work_order", "Stock Entry", "stock_entry")
def finish_production_run(
	work_order: str,
	qty: float,
	finished_batch: str | None = None,
	process_loss_qty: float = 0,
	request_id: str | None = None,
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

	order = frappe.get_doc("Work Order", work_order, for_update=True)
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
				flt(remaining),
				_production_item_uoms([order.production_item]).get(
					order.production_item, order.stock_uom
				),
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

"""Recall investigation: every batch a lot became, where it is, and who has it.

A Desk report rather than only an endpoint, because an investigation is an
artifact: it gets filtered, printed, exported and attached to a file that an
auditor reads months later.

The rows are built from the same permission-scoped trace the console uses, so
the report cannot show a batch, a delivery or a company the reader could not
open directly.

**Nothing is notified from here.** Telling customers is a decision with legal
and commercial weight; this report tells the plant who to call.
"""

import frappe
from frappe import _

from food_manufacturing.api.recall import get_recall


def execute(filters=None):
	filters = frappe._dict(filters or {})

	if not filters.get("batch") or not filters.get("company"):
		return _columns(), [], _("Choose a batch and a company to trace.")

	result = get_recall(filters.batch, filters.company)
	rows = _rows(result, filters.get("section"))

	return _columns(), rows, _message(result, filters.batch)


def _columns() -> list:
	return [
		{"label": _("Section"), "fieldname": "section", "fieldtype": "Data", "width": 110},
		{"label": _("Batch"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 170},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 180},
		{"label": _("Supplier Lot"), "fieldname": "supplier_lot_no", "fieldtype": "Data", "width": 130},
		{"label": _("Quality"), "fieldname": "quality_status", "fieldtype": "Data", "width": 100},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 170},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 170},
		{"label": _("Document"), "fieldname": "document", "fieldtype": "Dynamic Link", "options": "document_type", "width": 160},
		{"label": _("Document Type"), "fieldname": "document_type", "fieldtype": "Data", "width": 1, "hidden": 1},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 100, "precision": 3},
		{"label": _("UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 80},
		{"label": _("Note"), "fieldname": "note", "fieldtype": "Data", "width": 200},
	]


def _rows(result: dict, section: str | None) -> list:
	rows = []

	if section in (None, "", "Affected batches"):
		for batch in result["batches"]:
			rows.append({
				"section": _("Affected batch"),
				"batch_no": batch["name"],
				"item_code": batch["item"],
				"supplier_lot_no": batch.get("fm_supplier_lot_no"),
				"quality_status": batch.get("fm_quality_status"),
			})

	if section in (None, "", "Stock on hand"):
		for row in result.get("on_hand") or []:
			rows.append({
				"section": _("Stock on hand"),
				"batch_no": row["batch_no"],
				"item_code": row["item_code"],
				"warehouse": row["warehouse"],
				"qty": row["qty"],
				"stock_uom": row["stock_uom"],
				"note": _("Still in the plant - can be held"),
			})

	if section in (None, "", "Deliveries"):
		for row in result.get("deliveries") or []:
			returned = row["qty"] < 0 if "qty" in row else row["stock_qty"] < 0
			rows.append({
				"section": _("Delivered"),
				"batch_no": row["batch_no"],
				"item_code": row["item_code"],
				"customer": row["customer"],
				"document": row["delivery_note"],
				"document_type": "Delivery Note",
				"posting_date": row["posting_date"],
				"qty": row["stock_qty"],
				"stock_uom": row["stock_uom"],
				# A negative quantity is stock that came back, not stock owed.
				"note": _("Customer return") if returned else _("With the customer"),
			})

	return rows


def _message(result: dict, batch: str) -> str:
	parts = [
		_("Traced from batch {0}. Built from submitted stock transactions only.").format(
			frappe.bold(batch)
		)
	]

	if result.get("truncated"):
		parts.append(
			_("<b>The trace was cut short</b> at its depth limit, so this list may be incomplete.")
		)

	parts.append(_("No customer has been notified. This report says who to contact."))
	return " ".join(parts)

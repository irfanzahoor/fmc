"""Where a simulated rate comes from, and saying so.

ERPNext already resolves a BOM line's rate from the source the BOM declares -
valuation, last purchase rate or a price list. That logic is reused rather than
re-implemented: a second opinion on what an ingredient costs is exactly the kind
of duplication that drifts from the ledger.

What is added here is **provenance**. A simulation has to show where each number
came from, so every rate is returned with the source that produced it and a
reason when it could not be priced at all.
"""

import frappe
from frappe.utils import flt

#: BOM.rm_cost_as_per -> how to describe it to a reader.
SOURCE_LABEL = {
	"Valuation Rate": "Moving-average valuation",
	"Last Purchase Rate": "Last purchase rate",
	"Price List": "Price list",
	"Manual": "Manually set on the BOM",
}


def price_items(bom_doc, rows: list) -> dict:
	"""``{item_code: {"rate": float, "source": str}}`` for every BOM row.

	A row already carries the rate ERPNext resolved when the BOM was saved.
	That is the honest baseline - it is what the approved BOM costs - so it is
	used as-is, and only a row with no rate is re-resolved.
	"""
	out = {}
	label = SOURCE_LABEL.get(bom_doc.rm_cost_as_per, bom_doc.rm_cost_as_per)

	for row in rows:
		if not row.item_code or row.item_code in out:
			continue

		rate = flt(row.rate)
		if rate:
			out[row.item_code] = {
				"rate": rate,
				"source": f"{label}, as costed on this BOM",
			}
			continue

		resolved, source = _resolve(bom_doc, row, label)
		out[row.item_code] = {"rate": resolved, "source": source}

	return out


def _resolve(bom_doc, row, label: str) -> tuple:
	"""Ask ERPNext for a rate, and never let a pricing error kill the estimate.

	A missing price list, an item with no valuation anywhere - these are normal
	on a part-configured site. A simulation that refuses to open because one
	ingredient has no price is less useful than one that shows the line at zero
	and names the reason.
	"""
	from erpnext.manufacturing.doctype.bom.bom import get_bom_item_rate

	args = {
		"item_code": row.item_code,
		"qty": flt(row.qty) or 1,
		"uom": row.uom,
		"stock_uom": row.stock_uom,
		"conversion_factor": flt(row.conversion_factor) or 1,
		"company": bom_doc.company,
	}

	try:
		rate = flt(get_bom_item_rate(args, bom_doc))
	except Exception:
		frappe.log_error(
			title="Batchwell: could not price a BOM line",
			message=frappe.get_traceback(),
		)
		return 0.0, "Not priced: the price source raised an error"

	if not rate:
		return 0.0, f"Not priced: no {label.lower()} found for this item"

	return rate, label

"""Costing endpoints for the console.

Thin wrappers only: the arithmetic lives in ``food_manufacturing/costing/``, so
the same functions are callable from a report, a patch or a test without going
through HTTP.
"""

import frappe

from food_manufacturing.costing.simulator import simulate as _simulate


@frappe.whitelist()
def simulate_recipe_cost(
	bom: str,
	batch_qty: float | None = None,
	packs: list | str | None = None,
	overrides: dict | str | None = None,
	yield_percent: float | None = None,
	operating_cost: float | None = None,
) -> dict:
	"""What one batch of ``bom`` would cost. Read-only - see the simulator."""
	return _simulate(
		bom,
		batch_qty=batch_qty,
		packs=packs,
		overrides=overrides,
		yield_percent=yield_percent,
		operating_cost=operating_cost,
	)


@frappe.whitelist()
def get_costable_boms(company: str, item: str | None = None, limit: int = 50) -> list:
	"""Approved, active BOMs this user may cost, newest first."""
	frappe.has_permission("BOM", "read", throw=True)

	filters = {"company": company, "docstatus": 1, "is_active": 1}
	if item:
		filters["item"] = item

	return frappe.get_list(
		"BOM",
		filters=filters,
		fields=["name", "item", "item_name", "quantity", "uom", "currency", "rm_cost_as_per"],
		order_by="modified desc",
		limit=limit,
	)


@frappe.whitelist()
def plan_packaging(company: str, packs: list | str, loss_percent: float | None = None) -> dict:
	"""Requirements, stock position and shortages for a planned packing run."""
	from food_manufacturing.packaging.planning import plan

	packs = frappe.parse_json(packs) if isinstance(packs, str) else (packs or [])
	return plan(company, packs, loss_percent)


@frappe.whitelist(methods=["POST"])
def request_packaging_shortfall(
	company: str,
	packs: list | str,
	warehouse: str,
	loss_percent: float | None = None,
	schedule_date: str | None = None,
	request_id: str | None = None,
) -> dict:
	"""Propose a draft Material Request for the shortfall. Never submits it."""
	from food_manufacturing.packaging.requests import create_material_request

	packs = frappe.parse_json(packs) if isinstance(packs, str) else (packs or [])
	return create_material_request(
		company,
		packs,
		warehouse,
		loss_percent=loss_percent,
		schedule_date=schedule_date,
		request_id=request_id,
	)

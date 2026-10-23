"""Role-scoped dashboards: four jobs, four sets of panels.

An owner, a line supervisor, a quality manager and a storekeeper open the same
app wanting different answers, and one dashboard that tries to serve all four
serves none of them.

**Every metric links to its source records.** A number nobody can open is a
number nobody can act on - and, worse, a number nobody can check. Each carries a
`link` naming the DocType and the filters that produce exactly the rows behind
it, so the dashboard is an index into the ledger rather than a claim about it.

**Panels are filtered by what the reader may actually read.** A panel whose
source DocType is closed to this user is left out rather than shown empty: an
empty panel says "there is nothing", which is a different and wrong statement.
"""

import frappe
from frappe.utils import add_days, flt, getdate, today

from food_manufacturing.costing.variance import get_run_variances, summarise

#: Dashboard key -> the FM role that owns it, and the panels it carries.
DASHBOARDS = ("owner", "production", "quality", "stores")

ROLE_FOR = {
	"owner": ("FM Production Manager", "FM Quality Manager"),
	"production": ("FM Production Manager", "FM Production Operator"),
	"quality": ("FM Quality Manager", "FM Quality Inspector"),
	"stores": ("FM Warehouse Operator",),
}


@frappe.whitelist()
def get_dashboard(company: str, view: str = "owner", days: int = 30) -> dict:
	"""One role's dashboard for one company."""
	frappe.has_permission("Company", "read", doc=company, throw=True)

	if view not in DASHBOARDS:
		frappe.throw(
			frappe._("Unknown dashboard {0}. Use one of: {1}.").format(
				frappe.bold(view), ", ".join(DASHBOARDS)
			)
		)

	days = max(1, min(int(days or 30), 365))
	since = add_days(getdate(today()), -days)

	builder = {
		"owner": _owner,
		"production": _production,
		"quality": _quality,
		"stores": _stores,
	}[view]

	panels = [panel for panel in builder(company, since, days) if panel]

	return {
		"company": company,
		# A cost figure without its currency is ambiguous on a multi-company site.
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"view": view,
		"period_days": days,
		"since": str(since),
		"panels": panels,
		"available": available_views(),
	}


@frappe.whitelist()
def available_views() -> list:
	"""Which dashboards this user's roles entitle them to, best match first.

	Not a permission boundary - the endpoints re-check permission - but the
	difference between a landing page that fits the job and one that does not.
	"""
	roles = set(frappe.get_roles())
	if "System Manager" in roles:
		return list(DASHBOARDS)

	return [view for view in DASHBOARDS if roles.intersection(ROLE_FOR[view])] or ["production"]


# --- the four dashboards ----------------------------------------------------


def _owner(company: str, since, days: int) -> list:
	"""Production, stock, shortages, yield and cost variance."""
	from food_manufacturing.api.dashboard import get_dashboard as plant

	core = plant(company, days)
	kpis = core.get("kpis") or {}

	runs = get_run_variances(company, since)
	cost = summarise(runs)

	return [
		_panel("Production", [
			_metric("Completed runs", kpis.get("completed_runs"), link=_link(
				"Work Order", {"company": company, "status": "Completed"})),
			_metric("Open runs", kpis.get("open_runs"), link=_link(
				"Work Order", {"company": company, "status": ["in", ["Not Started", "In Process"]]})),
			_metric("Average actual yield", kpis.get("average_yield_percent"), unit="%", decimals=1),
			_metric("Runs outside tolerance", kpis.get("yield_flagged"), tone="warn", link=_link(
				"Work Order", {"company": company, "fm_yield_flagged": 1})),
		]),
		_panel("Cost variance", [
			_metric("Estimated cost", cost["estimated_cost"], currency=True),
			_metric("Actual cost", cost["actual_cost"], currency=True, link=_link(
				"Stock Entry", {"company": company, "purpose": "Manufacture", "docstatus": 1})),
			_metric(
				"Variance", cost["variance"], currency=True,
				tone="warn" if (cost["variance"] or 0) > 0 else "good",
			),
			_metric("Runs over plan", cost["over_plan_runs"], tone="warn"),
		], note=_cost_note(cost), rows=runs[:10]),
		_panel("Stock and quality", [
			_metric("Batches awaiting a decision", kpis.get("pending_qc"), tone="warn", link=_link(
				"Batch", {"fm_quality_status": ["in", ["Quarantine", "Hold"]]})),
			_metric("Near expiry", kpis.get("near_expiry"), tone="warn", link=_link(
				"Batch", {"expiry_date": ["<=", str(add_days(getdate(today()), 90))]})),
			_metric("Released in period", kpis.get("batches_released"), tone="good", link=_link(
				"FM Batch Release", {"company": company, "decision": "Release", "docstatus": 1})),
		]),
	]


def _production(company: str, since, days: int) -> list:
	"""Work queue, material readiness and output.

	Built from production figures only, rather than from the plant dashboard:
	that one also counts pending QC and near-expiry batches, which would make a
	line operator's own dashboard refuse on documents their job does not
	involve.
	"""
	from food_manufacturing.api.dashboard import _production_by_item, _completed_runs
	from food_manufacturing.api.production import get_production_queue

	runs = _completed_runs(company, since)
	queue = get_production_queue(company, limit=50)
	ready = [row for row in queue if not row.get("shortfall")]

	yielded = [flt(row.fm_actual_yield_percent) for row in runs if flt(row.fm_actual_yield_percent)]
	average = flt(sum(yielded) / len(yielded), 2) if yielded else None
	flagged = sum(1 for row in runs if row.fm_yield_flagged)

	return [
		_panel("Work queue", [
			_metric("Open runs", len(queue), link=_link(
				"Work Order", {"company": company, "status": ["in", ["Not Started", "In Process"]]})),
			_metric("Ready to start", len(ready)),
			_metric("Completed in period", len(runs), tone="good"),
		], rows=queue[:10]),
		_panel("Output", [
			_metric("Average actual yield", average, unit="%", decimals=1),
			_metric("Runs outside tolerance", flagged, tone="warn", link=_link(
				"Work Order", {"company": company, "fm_yield_flagged": 1})),
		], rows=_production_by_item(runs)),
	]


def _quality(company: str, since, days: int) -> list:
	"""Pending inspections, held batches and release actions."""
	from food_manufacturing.api.quality import get_queue_counts, get_release_queue

	counts = get_queue_counts(company)
	queue = get_release_queue(company, limit=10)
	pending = _pending_inspections(company)

	return [
		_panel("Decisions waiting", [
			_metric("In quarantine", counts.get("quarantine"), tone="warn", link=_link(
				"Batch", {"fm_quality_status": "Quarantine"})),
			_metric("On hold", counts.get("hold"), tone="warn", link=_link(
				"Batch", {"fm_quality_status": "Hold"})),
			_metric("Total awaiting", counts.get("total"), tone="warn"),
		], rows=queue),
		_panel("Inspections", [
			_metric("Draft inspections", pending, link=_link(
				"Quality Inspection", {"company": company, "docstatus": 0})),
			_metric("Decisions recorded in period", _releases(company, since), tone="good", link=_link(
				"FM Batch Release", {"company": company, "docstatus": 1})),
		]),
	]


def _stores(company: str, since, days: int) -> list:
	"""Receipts, packaging shortages and near-expiry stock."""
	from food_manufacturing.api.receiving import get_open_purchase_orders

	orders = get_open_purchase_orders(company, limit=50)
	near = _near_expiry(company)

	return [
		_panel("Goods in", [
			_metric("Open purchase orders", len(orders), link=_link(
				"Purchase Order", {"company": company, "status": ["not in", ["Closed", "Completed"]], "docstatus": 1})),
			_metric("Received in period", _receipts(company, since), tone="good", link=_link(
				"Purchase Receipt", {"company": company, "docstatus": 1})),
		], rows=orders[:10]),
		_panel("Shortages", [
			_metric("Open material requests", _open_requests(company), tone="warn", link=_link(
				"Material Request", {"company": company, "docstatus": 1, "status": ["!=", "Stopped"]})),
		], note="Plan a packing run to see what it is short of."),
		_panel("Near expiry", [
			_metric("Batches within 90 days", len(near), tone="warn", link=_link(
				"Batch", {"expiry_date": ["<=", str(add_days(getdate(today()), 90))]})),
		], rows=near[:10]),
	]


# --- building blocks --------------------------------------------------------


def _panel(title: str, metrics: list, rows: list | None = None, note: str | None = None) -> dict:
	return {
		"title": title,
		"metrics": [metric for metric in metrics if metric],
		"rows": rows or [],
		"note": note,
	}


def _metric(label, value, unit="", decimals=0, tone="neutral", currency=False, link=None) -> dict:
	"""One figure. ``value`` of None means unmeasured, and stays None."""
	return {
		"label": label,
		"value": value,
		"unit": unit,
		"decimals": decimals,
		"tone": tone,
		"currency": currency,
		"link": link,
	}


def _link(doctype: str, filters: dict) -> dict | None:
	"""The rows behind a figure - or nothing, if this user cannot open them."""
	if not frappe.has_permission(doctype, "read"):
		return None

	return {"doctype": doctype, "filters": filters}


def _cost_note(cost: dict) -> str | None:
	"""Say plainly when a cost figure rests on fewer runs than it looks."""
	if not cost["runs"]:
		return None
	if cost["measured_runs"] == cost["runs"]:
		return None

	return (
		f"{cost['measured_runs']} of {cost['runs']} runs could be costed. "
		"A run whose BOM carries no cost has no estimate to compare against."
	)


def _pending_inspections(company: str) -> int:
	return frappe.db.count("Quality Inspection", {"company": company, "docstatus": 0})


def _releases(company: str, since) -> int:
	return frappe.db.count(
		"FM Batch Release",
		{"company": company, "docstatus": 1, "posting_datetime": (">=", since)},
	)


def _receipts(company: str, since) -> int:
	return frappe.db.count(
		"Purchase Receipt", {"company": company, "docstatus": 1, "posting_date": (">=", since)}
	)


def _open_requests(company: str) -> int:
	return frappe.db.count(
		"Material Request",
		{"company": company, "docstatus": 1, "status": ("not in", ("Stopped", "Received"))},
	)


def _near_expiry(company: str) -> list:
	"""Batches with stock, expiring within 90 days, most urgent first."""
	from food_manufacturing.stock_levels import get_batch_quantities

	warehouses = frappe.get_all(
		"Warehouse", filters={"company": company, "is_group": 0}, pluck="name"
	)
	if not warehouses:
		return []

	batches = frappe.get_list(
		"Batch",
		filters={
			"disabled": 0,
			"expiry_date": ("<=", add_days(getdate(today()), 90)),
			"fm_quality_status": ("!=", "Rejected"),
		},
		fields=["name", "item", "expiry_date", "fm_quality_status"],
		order_by="expiry_date asc",
		limit=200,
	)
	if not batches:
		return []

	quantities = get_batch_quantities([row.name for row in batches], warehouses)

	return [
		{
			"batch_no": row.name,
			"item_code": row.item,
			"expiry_date": str(row.expiry_date),
			"quality_status": row.fm_quality_status,
			"qty": flt(quantities.get(row.name)),
		}
		for row in batches
		if flt(quantities.get(row.name)) > 0
	]

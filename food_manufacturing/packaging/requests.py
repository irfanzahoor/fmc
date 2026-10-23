"""Turning a shortage into a Material Request somebody can review.

The request is a **standard ERPNext Material Request, left as a draft**. This
app does not approve, submit or order anything: a planner proposes, a buyer
decides. Submitting on the operator's behalf would put purchasing authority
behind a shop-floor button.

Duplicates are prevented twice over, because one way is not enough:

* **By arithmetic.** The planner nets off ``Bin.indented_qty``, so a shortage
  already requested is no longer a shortage. Planning the same run twice
  produces nothing the second time, which is the behaviour a planner expects
  without having to know about keys.
* **By key.** Arithmetic loses a race between two people clicking at once, so
  the plan also carries an idempotency key. A repeat of the same request
  returns the Material Request the first call created.
"""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, today

from food_manufacturing.packaging.planning import plan

#: How far out a proposed request is dated when the caller says nothing.
DEFAULT_LEAD_DAYS = 7


def create_material_request(
	company: str,
	packs: list,
	warehouse: str,
	loss_percent: float | None = None,
	schedule_date: str | None = None,
	request_id: str | None = None,
) -> dict:
	"""Propose a draft Material Request for whatever the plan is short of."""
	frappe.has_permission("Material Request", "create", throw=True)
	frappe.has_permission("Warehouse", "read", doc=warehouse, throw=True)
	_check_company(company, warehouse)

	key = _key(company, packs, warehouse, loss_percent, request_id)
	existing = _existing(key)
	if existing:
		return {"material_request": existing, "created": False, "shortages": None}

	result = plan(company, packs, loss_percent)
	shortages = [line for line in result["lines"] if line["shortage_qty"] > 0]

	if not shortages:
		return {"material_request": None, "created": False, "shortages": []}

	doc = _draft(company, warehouse, shortages, schedule_date, key)

	return {
		"material_request": doc.name,
		"created": True,
		"shortages": shortages,
		"loss_percent": result["loss_percent"],
		"notes": result["notes"],
	}


def _check_company(company: str, warehouse: str) -> None:
	"""A plan may not request stock into another company's warehouse."""
	owner = frappe.db.get_value("Warehouse", warehouse, "company")
	if owner != company:
		frappe.throw(
			_("Warehouse {0} belongs to {1}, not to {2}.").format(
				frappe.bold(warehouse), owner, company
			),
			frappe.PermissionError,
		)


def _key(company, packs, warehouse, loss_percent, request_id) -> str:
	"""A stable fingerprint of this plan, scoped to the user.

	Without an explicit ``request_id`` the plan's own contents are the key, so
	two identical plans collapse into one request. With one, the caller
	controls retry grouping - a deliberate second request for the same plan
	passes a new id.
	"""
	payload = json.dumps(
		{
			"company": company,
			"warehouse": warehouse,
			"loss_percent": loss_percent,
			"request_id": request_id,
			"packs": sorted(
				(row.get("item_code"), flt(row.get("qty"))) for row in packs if row.get("item_code")
			),
		},
		sort_keys=True,
		default=str,
	)
	return hashlib.sha256(f"{frappe.session.user}:{payload}".encode()).hexdigest()


def _existing(key: str) -> str | None:
	"""A Material Request this plan already produced, if it still stands.

	A cancelled request is not a reason to refuse a new one - the plan is still
	short. A draft or submitted one is.
	"""
	name = frappe.db.get_value(
		"Material Request",
		{"fm_operation_key": key, "docstatus": ("<", 2)},
		"name",
		for_update=True,
	)
	if not name:
		return None

	frappe.has_permission("Material Request", "read", doc=name, throw=True)
	return name


def _draft(company, warehouse, shortages, schedule_date, key):
	"""The draft itself. Inserted, never submitted."""
	needed = getdate(schedule_date) if schedule_date else add_days(getdate(today()), DEFAULT_LEAD_DAYS)

	doc = frappe.new_doc("Material Request")
	doc.material_request_type = "Purchase"
	doc.company = company
	doc.transaction_date = today()
	doc.schedule_date = needed
	doc.fm_operation_key = key

	for line in shortages:
		doc.append(
			"items",
			{
				"item_code": line["item_code"],
				"qty": flt(line["shortage_qty"]),
				"uom": line["uom"],
				"stock_uom": line["uom"],
				"conversion_factor": 1,
				"warehouse": warehouse,
				"schedule_date": needed,
			},
		)

	doc.insert()
	return doc

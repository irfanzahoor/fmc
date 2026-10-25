"""Run a recall drill and record what it found.

The trace itself is `api/recall.get_recall`, unchanged — a drill that used a
different code path from a real investigation would prove nothing about the real
one. This module times that call, measures the lot's mass balance alongside it,
and writes both into an `FM Recall Drill` the plant can hand to an auditor.

Permission is deliberately strict: creating the record requires create rights
on `FM Recall Drill`, and the trace re-checks read permission on every DocType
it touches, because `get_recall` does. A drill is also a read of the whole
downstream customer list, which is not something every console user should be
able to produce.
"""

import json
import time

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from food_manufacturing.api.recall import get_recall
from food_manufacturing.production.mass_balance import get_mass_balance

#: Drill types the record accepts, matching the DocType's own Select options.
DRILL_TYPES = ("Mock Drill", "Actual Recall")


@frappe.whitelist(methods=["POST"])
def run_recall_drill(batch: str, company: str, drill_type: str = "Mock Drill", findings: str | None = None):
	"""Trace ``batch``, time it, and file the result as a draft drill.

	Returns the created document's name and the figures it recorded. The
	document is left **in draft**: submitting it is a signature, and signing on
	an operator's behalf is not this endpoint's business.
	"""
	frappe.has_permission("FM Recall Drill", "create", throw=True)

	if drill_type not in DRILL_TYPES:
		frappe.throw(
			_("Unknown drill type {0}. Use one of: {1}.").format(
				frappe.bold(drill_type), ", ".join(DRILL_TYPES)
			)
		)

	started = now_datetime()

	# monotonic, not wall clock: the elapsed figure goes on an audit record and
	# must not be distorted by a clock adjustment mid-trace.
	clock = time.monotonic()
	trace = get_recall(batch, company)
	seconds = time.monotonic() - clock

	balance = get_mass_balance(batch, company)
	disposition = balance["disposition"]

	customers = {
		row.get("customer") for row in trace["deliveries"] if row.get("customer")
	}

	inward = flt(disposition["inward_qty"])
	residual = abs(flt(disposition["residual_qty"]))
	# No inward quantity means nothing to account for; reporting 0% accounted
	# would read as a failure when there is simply no stock in the figure.
	accounted = 100.0 if not inward else max(0.0, 100.0 - (residual / inward * 100.0))

	doc = frappe.new_doc("FM Recall Drill")
	doc.batch = batch
	doc.company = company
	doc.drill_type = drill_type
	doc.findings = findings
	doc.started_at = started
	doc.seconds_to_trace = seconds
	doc.affected_batches = len(trace["batches"])
	doc.affected_deliveries = len({row["delivery_note"] for row in trace["deliveries"]})
	doc.affected_customers = len(customers)
	doc.truncated = 1 if trace["truncated"] else 0
	doc.trace_complete = 0 if trace["truncated"] else 1
	doc.stock_uom = disposition["stock_uom"]
	doc.inward_qty = inward
	doc.dispatched_qty = flt(disposition["dispatched_qty"])
	doc.on_hand_qty = flt(disposition["on_hand_qty"])
	doc.in_rejected_warehouse = flt(disposition["in_rejected_warehouse"])
	doc.accounted_percent = accounted
	doc.balance_flagged = 1 if balance["flagged"] else 0
	doc.trace_snapshot = json.dumps(
		{"trace": trace, "balance": balance}, indent=1, default=str, sort_keys=True
	)
	doc.insert()

	return {
		"name": doc.name,
		"drill_type": doc.drill_type,
		"seconds_to_trace": flt(doc.seconds_to_trace),
		"affected_batches": doc.affected_batches,
		"affected_deliveries": doc.affected_deliveries,
		"affected_customers": doc.affected_customers,
		"accounted_percent": flt(doc.accounted_percent),
		"balance_flagged": bool(doc.balance_flagged),
		"trace_complete": bool(doc.trace_complete),
	}


@frappe.whitelist()
def get_drill_history(company: str, limit: int = 20):
	"""Past drills for a company, newest first.

	The point of a history is the trend: an auditor asks how often drills are
	run and whether the time to trace is getting better, not just what the last
	one said.
	"""
	frappe.has_permission("FM Recall Drill", "read", throw=True)
	frappe.has_permission("Company", "read", doc=company, throw=True)

	return frappe.get_list(
		"FM Recall Drill",
		filters={"company": company, "docstatus": 1},
		fields=[
			"name",
			"batch",
			"item_code",
			"drill_type",
			"started_at",
			"conducted_by",
			"seconds_to_trace",
			"affected_batches",
			"affected_deliveries",
			"affected_customers",
			"accounted_percent",
			"balance_flagged",
			"trace_complete",
		],
		order_by="started_at desc",
		limit_page_length=min(int(limit), 100),
	)

"""Raising a Quality Inspection against a batch.

The app never had a way to *create* one: it checked for a matching accepted
inspection before release, but an inspector had to go and build that inspection
in the Desk by hand. This closes that, and does it by driving ERPNext's own
Quality Inspection rather than modelling a second one.

**No limit is written here.** Parameters, minimum and maximum values and
acceptance formulas live in a Quality Inspection Template that the plant
configures. An item with no template cannot be inspected through this module,
and it says so - inventing a moisture ceiling or a plate count would be a food
safety claim this app has no standing to make.
"""

import frappe
from frappe import _
from frappe.utils import flt, today

#: What the plant calls a stage -> ERPNext's own inspection_type.
STAGES = {
	"Incoming": "Incoming",
	"In Process": "In Process",
	"Finished": "Outgoing",
}

#: Which documents each stage may be an inspection *of*.
#:
#: v16 makes `reference_type`, `reference_name` and `sample_size` mandatory on a
#: Quality Inspection, which is the right constraint: an inspection is always of
#: something that happened. These pairings keep a finished-product check from
#: being filed against a purchase receipt.
STAGE_REFERENCES = {
	"Incoming": ("Purchase Receipt", "Purchase Invoice", "Subcontracting Receipt", "Stock Entry"),
	"In Process": ("Stock Entry", "Job Card"),
	"Finished": ("Stock Entry", "Delivery Note", "Sales Invoice"),
}


def create_inspection(
	batch: str,
	stage: str,
	reference_type: str,
	reference_name: str,
	sample_size: float,
	readings: list | None = None,
	remarks: str | None = None,
	status: str | None = None,
	submit: bool = False,
) -> dict:
	"""Raise a Quality Inspection for ``batch`` at ``stage``.

	The source document and the sample size are required, not optional: an
	inspection with neither is a claim about a batch with nothing behind it,
	and v16 refuses to save one anyway.

	``readings`` is ``[{"specification": ..., "reading_value": ...}]`` - values
	only. Which specifications exist, and what counts as passing, come from the
	template.
	"""
	frappe.has_permission("Quality Inspection", "create", throw=True)

	inspection_type = STAGES.get(stage)
	if not inspection_type:
		frappe.throw(
			_("Unknown inspection stage {0}. Use one of: {1}.").format(
				frappe.bold(stage), ", ".join(STAGES)
			)
		)

	if flt(sample_size) <= 0:
		frappe.throw(_("Sample size must be greater than zero."))

	allowed = STAGE_REFERENCES[stage]
	if reference_type not in allowed:
		frappe.throw(
			_("An {0} check cannot be filed against a {1}. Use one of: {2}.").format(
				stage, reference_type, ", ".join(allowed)
			)
		)

	info = _batch(batch)
	template = _template(info.item)

	doc = frappe.new_doc("Quality Inspection")
	doc.inspection_type = inspection_type
	doc.report_date = today()
	doc.item_code = info.item
	doc.batch_no = batch
	doc.company = info.company
	doc.quality_inspection_template = template
	doc.inspected_by = frappe.session.user
	doc.remarks = remarks
	doc.sample_size = flt(sample_size)

	_check_reference(reference_type, reference_name)
	doc.reference_type = reference_type
	doc.reference_name = reference_name

	# ERPNext fills `readings` from the template during validate, so the rows
	# are populated by its own code and only the measured values are applied
	# here. Reimplementing that copy is how the two drift apart.
	doc.insert()
	_apply_readings(doc, readings or [])

	if status:
		doc.status = status
	doc.save()

	if submit:
		doc.submit()

	return {
		"quality_inspection": doc.name,
		"status": doc.status,
		"inspection_type": doc.inspection_type,
		"template": template,
		"docstatus": doc.docstatus,
	}


def _batch(batch: str):
	"""The batch, if this user may read it."""
	frappe.has_permission("Batch", "read", doc=batch, throw=True)

	row = frappe.db.get_value("Batch", batch, ["name", "item", "fm_quality_status"], as_dict=True)
	if not row:
		frappe.throw(_("Batch {0} does not exist.").format(frappe.bold(batch)))

	row.company = _company_of(batch)
	return row


def _company_of(batch: str) -> str | None:
	"""The company whose stock this batch sits in.

	A Batch has no company of its own, so it is read off the stock that exists -
	which is also the only company whose quality team has any business
	inspecting it.
	"""
	return frappe.db.get_value(
		"Stock Ledger Entry",
		{"batch_no": batch, "is_cancelled": 0},
		"company",
		order_by="posting_date asc, creation asc",
	)


def _template(item_code: str) -> str:
	"""The item's Quality Inspection Template, which carries the limits."""
	template = frappe.db.get_value("Item", item_code, "quality_inspection_template")
	if not template:
		frappe.throw(
			_(
				"Item {0} has no Quality Inspection Template. Add one with the "
				"parameters and limits this plant inspects against - this app "
				"does not supply them."
			).format(frappe.bold(item_code))
		)

	return template


def _check_reference(reference_type: str, reference_name: str) -> None:
	"""A reference must be a document this user may actually read."""
	if not frappe.db.exists(reference_type, reference_name):
		frappe.throw(
			_("{0} {1} does not exist.").format(reference_type, frappe.bold(reference_name))
		)
	frappe.has_permission(reference_type, "read", doc=reference_name, throw=True)


def _apply_readings(doc, readings: list) -> None:
	"""Write measured values onto the template's rows.

	A value for a parameter the template does not define is refused rather than
	appended: the template is the list of what gets measured, and quietly adding
	a row would let an inspection assert a limit nobody configured.
	"""
	if not readings:
		return

	by_spec = {row.specification: row for row in doc.get("readings") or []}

	for entry in readings:
		spec = entry.get("specification")
		row = by_spec.get(spec)
		if not row:
			frappe.throw(
				_("{0} is not a parameter on template {1}.").format(
					frappe.bold(spec), frappe.bold(doc.quality_inspection_template)
				)
			)

		if "reading_value" in entry:
			row.reading_value = entry["reading_value"]
		if "reading_1" in entry:
			row.reading_1 = entry["reading_1"]
		if entry.get("status"):
			row.status = entry["status"]


def get_inspections(batch: str, limit: int = 20) -> list:
	"""Every inspection raised against a batch, whatever its verdict.

	Deliberately not filtered to Accepted. A rejected or cancelled inspection is
	exactly what a quality manager needs to see before deciding, and hiding it
	would make the history a record of good news only.
	"""
	frappe.has_permission("Batch", "read", doc=batch, throw=True)

	item = frappe.db.get_value("Batch", batch, "item")
	return frappe.get_list(
		"Quality Inspection",
		filters={"item_code": item, "batch_no": batch},
		fields=[
			"name",
			"status",
			"docstatus",
			"inspection_type",
			"report_date",
			"inspected_by",
			"quality_inspection_template",
			"sample_size",
			"remarks",
		],
		order_by="report_date desc, creation desc",
		limit=limit,
	)


def get_readings(inspection: str) -> list:
	"""The measured values of one inspection, with the limits they were read against."""
	frappe.has_permission("Quality Inspection", "read", doc=inspection, throw=True)

	doc = frappe.get_doc("Quality Inspection", inspection)
	doc.check_permission("read")

	return [
		{
			"specification": row.specification,
			"value": row.value,
			"min_value": row.min_value,
			"max_value": row.max_value,
			"reading_value": row.reading_value,
			"status": row.status,
			"numeric": row.numeric,
		}
		for row in doc.get("readings") or []
	]

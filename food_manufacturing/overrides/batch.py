"""Batch extensions: the quality fields are app-controlled state, not user input.

``fm_quality_status`` and the release fields beside it are marked ``read_only`` on the
form. That keeps them out of the way of someone filling in a Batch, but
``read_only`` is an instruction to the form, not a permission: ``/api/resource``,
``frappe.client.set_value``, Data Import and a Server Script all write a
read-only field without complaint. A release gate resting on it rests on
nothing - anyone who may write a Batch could mark one ``Released`` with no
inspection and no FM Batch Release to say who decided.

This is that boundary, wired through ``doc_events`` so it holds on every path
that saves the document. The app's own writers deliberately do not pass through
it: FM Batch Release and the receiving and production stamps use
``frappe.db.set_value``, which writes the column without loading the document.
Code that must save the document itself, and a deliberate administrative
correction from ``bench console``, set ``frappe.flags.fm_batch_quality_write``.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime

#: Fields whose only writers are FM Batch Release and the app's own stamps.
#:
#: ``fm_supplier_lot_no`` is deliberately not among them. It is the supplier's
#: own reference, stamped from the Purchase Receipt rather than decided by
#: anyone, and it gates nothing. Guarding it only made a lot number that was
#: mistyped on a submitted receipt impossible to correct anywhere - the release
#: gate gained nothing and traceability lost a correction.
PROTECTED_FIELDS = (
	"fm_quality_status",
	"fm_last_release",
	"fm_released_by",
	"fm_released_on",
)

#: Fields holding a moment rather than a string, compared as datetimes so a
#: round trip through the form does not read as a change.
DATETIME_FIELDS = ("fm_released_on",)


def validate(doc, method=None):
	guard_quality_fields(doc)


def guard_quality_fields(doc) -> None:
	"""Refuse a document save that changes a quality field.

	Install, migrate and patch runs are exempt: they are the app writing its own
	schema and data, not a user editing a batch.
	"""
	if frappe.flags.fm_batch_quality_write:
		return

	if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch:
		return

	changed = _changed_fields(doc)
	if not changed:
		return

	meta = frappe.get_meta(doc.doctype)
	labels = [frappe.bold(_(meta.get_label(fieldname))) for fieldname in changed]

	# ValidationError, deliberately, and not PermissionError: nobody may write
	# these fields down this path - a System Manager is refused exactly as an
	# operator is - so the refusal is a rule about the write, not a statement
	# about who the caller is. The guards in recipe_access and costing.simulator
	# do raise PermissionError, because those genuinely do turn on the caller.
	frappe.throw(
		_(
			"{0} is set by FM Batch Release, which records who decided and why. "
			"Record a quality decision instead of editing the batch."
		).format(", ".join(labels)),
		title=_("Quality Status Is Not Editable"),
	)


def _changed_fields(doc) -> list:
	"""Protected fields this save would change, in field order."""
	before = _stored_values(doc)

	return [
		fieldname
		for fieldname in PROTECTED_FIELDS
		if not _same(fieldname, before.get(fieldname), doc.get(fieldname))
	]


def _stored_values(doc) -> dict:
	"""What the database currently holds, in one query.

	A new Batch holds nothing, so every protected field must arrive blank: a
	batch cannot be born Released any more than it can be edited into it.
	"""
	if doc.is_new():
		return {}

	values = frappe.db.get_value("Batch", doc.name, PROTECTED_FIELDS, as_dict=True)
	return values or {}


def _same(fieldname: str, before, after) -> bool:
	if fieldname in DATETIME_FIELDS:
		return _as_datetime(before) == _as_datetime(after)

	return (before or "") == (after or "")


def _as_datetime(value):
	return get_datetime(value) if value else None

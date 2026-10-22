import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from food_manufacturing.food_manufacturing_setup.doctype.fm_manufacturing_policy.fm_manufacturing_policy import (
	get_policy,
)

#: Quality status a decision results in.
STATUS_BY_DECISION = {
	"Release": "Released",
	"Hold": "Hold",
	"Reject": "Rejected",
}

#: Permitted transitions. A blank current status means the batch is not yet
#: quality-managed, so any first decision is allowed. "Rejected" is terminal:
#: undoing it means cancelling the decision that caused it, which preserves the
#: audit trail rather than overwriting it.
ALLOWED_TRANSITIONS = {
	"": {"Released", "Hold", "Rejected"},
	"Quarantine": {"Released", "Hold", "Rejected"},
	"Hold": {"Released", "Rejected"},
	"Released": {"Hold", "Rejected"},
	"Rejected": set(),
}


class FMBatchRelease(Document):
	def validate(self):
		self.set_defaults()
		self.validate_batch()
		self.validate_reason()
		self.validate_inspection_requirement()
		self.validate_transition(self.get_current_status())

	def before_submit(self):
		# Recorded at submit so the audit trail names the user who actually
		# authorised the decision, not whoever drafted it.
		self.decided_by = frappe.session.user

	def on_submit(self):
		self.apply_decision()

	def on_cancel(self):
		self.revert_decision()

	# -- validation ----------------------------------------------------------

	def set_defaults(self):
		if not self.posting_datetime:
			self.posting_datetime = now_datetime()

		if not self.decided_by:
			self.decided_by = frappe.session.user

	def validate_batch(self):
		if frappe.db.get_value("Batch", self.batch, "disabled"):
			frappe.throw(
				_("Batch {0} is disabled and cannot receive a quality decision.").format(
					frappe.bold(self.batch)
				)
			)

	def validate_reason(self):
		if self.decision in ("Hold", "Reject") and not (self.reason or "").strip():
			frappe.throw(
				_("A reason is mandatory when the decision is {0}.").format(_(self.decision)),
				title=_("Reason Required"),
			)

	def validate_inspection_requirement(self):
		"""Policy may require an inspection before a batch can be released."""
		if self.decision != "Release":
			return

		policy = get_policy(self.company)
		if not policy.require_incoming_inspection:
			return

		if not self.quality_inspection:
			frappe.throw(
				_("A Quality Inspection is required to release a batch under the policy for {0}.").format(
					frappe.bold(self.company)
				),
				title=_("Inspection Required"),
			)

		status = frappe.db.get_value("Quality Inspection", self.quality_inspection, ["status", "docstatus"], as_dict=True)
		if not status or status.docstatus != 1:
			frappe.throw(
				_("Quality Inspection {0} must be submitted before it can support a release.").format(
					frappe.bold(self.quality_inspection)
				)
			)

		if status.status == "Rejected":
			frappe.throw(
				_("Quality Inspection {0} was rejected, so this batch cannot be released.").format(
					frappe.bold(self.quality_inspection)
				)
			)

	def validate_transition(self, current_status: str):
		new_status = STATUS_BY_DECISION[self.decision]
		allowed = ALLOWED_TRANSITIONS.get(current_status or "", set())

		if new_status not in allowed:
			frappe.throw(
				_("A batch that is {0} cannot be changed to {1}.").format(
					frappe.bold(_(current_status or "unmanaged")), frappe.bold(_(new_status))
				),
				title=_("Invalid Quality Transition"),
			)

	def get_current_status(self, for_update: bool = False) -> str:
		return (
			frappe.db.get_value("Batch", self.batch, "fm_quality_status", for_update=for_update) or ""
		)

	# -- effects -------------------------------------------------------------

	def apply_decision(self):
		"""Write the decision onto the batch.

		The batch row is locked for the remainder of the transaction, so two
		concurrent releases of the same batch serialise and the second one sees
		the first one's status and fails the transition check. A retried request
		is therefore safe: it either re-reads the same state and is rejected as
		an invalid transition, or it is the only writer.
		"""
		current_status = self.get_current_status(for_update=True)
		self.validate_transition(current_status)

		new_status = STATUS_BY_DECISION[self.decision]
		self.db_set("previous_status", current_status, update_modified=False)

		values = {
			"fm_quality_status": new_status,
			"fm_last_release": self.name,
		}
		if self.decision == "Release":
			values["fm_released_by"] = self.decided_by
			values["fm_released_on"] = self.posting_datetime
		else:
			values["fm_released_by"] = None
			values["fm_released_on"] = None

		self.update_batch(values)

	def revert_decision(self):
		"""Restore the status this batch had before the cancelled decision."""
		self.get_current_status(for_update=True)

		previous = self.previous_status or "Quarantine"
		values = {
			"fm_quality_status": previous,
			"fm_last_release": None,
			"fm_released_by": None,
			"fm_released_on": None,
		}

		if previous == "Released":
			# The batch was already released before this decision; preserve that.
			earlier = frappe.db.get_value(
				"FM Batch Release",
				{
					"batch": self.batch,
					"decision": "Release",
					"docstatus": 1,
					"name": ("!=", self.name),
				},
				["name", "decided_by", "posting_datetime"],
				order_by="posting_datetime desc",
				as_dict=True,
			)
			if earlier:
				values["fm_last_release"] = earlier.name
				values["fm_released_by"] = earlier.decided_by
				values["fm_released_on"] = earlier.posting_datetime

		self.update_batch(values)

	def update_batch(self, values: dict) -> None:
		"""Set fields on the submitted Batch document.

		``Batch`` is not submittable in ERPNext, but the fields are marked
		``allow_on_submit`` and written through ``frappe.db.set_value`` because
		the quality status is app-controlled state rather than user input - the
		custom field is read-only on the form precisely so that only this
		document can change it.
		"""
		frappe.db.set_value("Batch", self.batch, values, update_modified=True)
		frappe.clear_document_cache("Batch", self.batch)

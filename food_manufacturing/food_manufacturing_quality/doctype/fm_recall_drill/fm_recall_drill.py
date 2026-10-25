"""A recorded recall exercise.

Everything else in this app derives traceability from the ledger and stores
nothing, so that it cannot drift. A drill is the one case where storing is the
point: the evidence an auditor asks for is *what the trace showed on the day it
was run*, and re-deriving it today would answer a different question — the
chain may have moved on, stock may have been consumed, batches may have been
released since.

So the figures and the snapshot are written once, at submit, and are read-only
afterwards. The document records an exercise; it does not perform a recall, and
it notifies nobody. Telling a customer has legal and commercial weight and
stays a human decision, which is the same line `docs/BACKLOG.md` already draws.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class FMRecallDrill(Document):
	def validate(self):
		self.set_item()
		self.validate_batch_company()

	def set_item(self):
		info = frappe.db.get_value("Batch", self.batch, ["item", "item_name"], as_dict=True)
		if not info:
			frappe.throw(_("Batch {0} does not exist.").format(frappe.bold(self.batch)))

		self.item_code = info.item
		self.item_name = info.item_name or frappe.db.get_value("Item", info.item, "item_name")

	def validate_batch_company(self):
		"""The drill has to be run where the stock actually is.

		A batch carries no company of its own, so the check is that the company
		has some ledger history for it. Without this a drill could be filed
		against a company that never handled the lot and would report zeroes
		that look like a clean result.
		"""
		if not self.company:
			return

		moved = frappe.db.exists(
			"Stock Ledger Entry",
			{"batch_no": self.batch, "company": self.company, "is_cancelled": 0},
		)
		if moved:
			return

		# The batch may only ever have moved inside a Serial and Batch Bundle,
		# in which case the ledger row carries the bundle rather than the batch.
		from food_manufacturing.production.genealogy import get_batch_movements

		if not get_batch_movements({self.batch}, self.company, "Stock Entry") and not get_batch_movements(
			{self.batch}, self.company, "Purchase Receipt"
		):
			frappe.throw(
				_("Batch {0} has no stock history in {1}, so there is nothing to trace.").format(
					frappe.bold(self.batch), frappe.bold(self.company)
				)
			)

	def before_submit(self):
		if not self.trace_snapshot:
			frappe.throw(
				_("Run the drill before submitting it, so the record carries a trace."),
			)

		# Named at submit, so the record credits whoever stood behind the
		# result rather than whoever opened the form.
		self.conducted_by = frappe.session.user

	def on_submit(self):
		if flt(self.accounted_percent) < 100 or self.balance_flagged or not self.trace_complete:
			# Worth saying out loud at the moment of signing: a drill that
			# records an incomplete trace is a finding, not a pass.
			frappe.msgprint(
				_("This drill recorded an incomplete result. Its findings should say what will be done."),
				indicator="orange",
				alert=True,
			)

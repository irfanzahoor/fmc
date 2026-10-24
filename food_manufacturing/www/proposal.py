"""The capability document, served as a page and as a PDF.

One source for both: the page at `/batchwell-proposal` and the PDF download are
the same template, so a vendor reading the link and a vendor reading the
attachment cannot be sent different claims.

Everything in it is a statement about what the app does. No certification,
accreditation or compliance claim appears anywhere - the app enforces the limits
a plant configures and makes no assertion about food safety standards.
"""

import frappe
from frappe import _
from frappe.utils import today

#: Figures quoted in the document. Kept here so the page and the PDF cannot
#: drift, and so updating one number is one edit.
FACTS = {
	"frappe_version": "16",
	"erpnext_version": "16",
	"tests": 347,
	"screens": 9,
	"roles": 6,
}

no_cache = 1


def get_context(context):
	"""Public by design: a proposal is sent to people without a login."""
	context.no_cache = 1
	context.facts = FACTS
	context.generated_on = today()
	context.company = _requesting_company()
	return context


def _requesting_company() -> str | None:
	"""The reader's own company name, when they are signed in.

	A signed-in user sees the document addressed to their company; an anonymous
	visitor sees the generic version. Nothing is invented either way.
	"""
	if frappe.session.user == "Guest":
		return None

	return frappe.defaults.get_user_default("Company")


@frappe.whitelist(allow_guest=True)
def download():
	"""The same document as a PDF attachment."""
	from frappe.utils.pdf import get_pdf

	context = frappe._dict(
		facts=FACTS,
		generated_on=today(),
		company=_requesting_company(),
		for_print=True,
	)
	# The *print* template, not the body: the body has no <head>, so rendering
	# it alone produced a correct but completely unstyled PDF.
	html = frappe.render_template("templates/pages/proposal_print.html", context)

	frappe.local.response.filename = "Batchwell-capability-document.pdf"
	frappe.local.response.filecontent = get_pdf(
		html,
		options={
			"page-size": "A4",
			# Zero, so the green cover bleeds to the top edge of page one.
			"margin-top": "0mm",
			"margin-bottom": "16mm",
			"margin-left": "0mm",
			"margin-right": "0mm",
			"print-media-type": None,
			"encoding": "UTF-8",
		},
	)
	frappe.local.response.type = "pdf"

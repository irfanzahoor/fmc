"""Work Order guard: production only against an approved recipe.

Registered through ``doc_events`` so the rule holds on the API and import paths
as well as the form.
"""

import frappe
from frappe import _

from food_manufacturing.packaging.validation import validate_packaging_work_order


def validate(doc, method=None):
	validate_recipe_approved(doc)
	validate_packaging_work_order(doc)


def validate_recipe_approved(doc) -> None:
	"""A BOM generated from an FM Recipe may only be used while approved.

	BOMs that have no recipe are left alone: this app does not take over every
	BOM on the site, only the ones it generated.
	"""
	if not doc.bom_no:
		return

	recipe = frappe.db.get_value("BOM", doc.bom_no, "fm_recipe")
	if not recipe:
		return

	status, docstatus = frappe.db.get_value("FM Recipe", recipe, ["status", "docstatus"])

	if docstatus != 1:
		frappe.throw(
			_("Recipe {0} behind BOM {1} is not submitted, so it cannot be produced.").format(
				frappe.bold(recipe), frappe.bold(doc.bom_no)
			),
			title=_("Recipe Not Approved"),
		)

	if status != "Approved":
		frappe.throw(
			_("Recipe {0} behind BOM {1} is {2}. Only an approved recipe may be produced.").format(
				frappe.bold(recipe), frappe.bold(doc.bom_no), frappe.bold(_(status))
			),
			title=_("Recipe Not Approved"),
		)

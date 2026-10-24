"""Who may see a formula, asked in one place.

An FM Recipe keeps its ingredient lines at ``permlevel`` 1, which is what stops
the recipe form, ``/api/resource``, a report and an export from handing the
percentages to someone who may not have them. That protection is only as good as
the places that can *reconstruct* the same numbers from somewhere else, and
quantities are percentages once you know the batch size: a blend of 60 kg chilli
in a 100 kg batch is the formula, written in kilograms.

So every endpoint that would quote per-ingredient quantities asks this question
first, and the answer is the recipe's own permlevel rather than a second rule
that could drift away from it.
"""

import frappe
from frappe import _


def may_see_formula(bom: str | None) -> bool:
	"""Whether this user may see the per-ingredient lines behind ``bom``.

	A BOM that no submitted FM Recipe generated is ordinary ERPNext data and is
	not gated here - this app does not decide who reads other people's BOMs.
	"""
	if not bom:
		return True

	if not frappe.db.exists("FM Recipe", {"bom": bom, "docstatus": 1}):
		return True

	return 1 in frappe.get_meta("FM Recipe").get_permlevel_access("read")


def require_formula_access(bom: str, action: str) -> None:
	"""Refuse ``action`` unless this user may see the formula behind ``bom``.

	Used where the result would carry the quantities rather than merely the
	totals - a refusal the caller can read is better than a silently emptied
	response that looks like an answer.
	"""
	if may_see_formula(bom):
		return

	frappe.throw(
		_("{0} needs access to the confidential formula of this recipe.").format(action),
		frappe.PermissionError,
		title=_("Formula Not Accessible"),
	)

"""BOM extensions: the formula survives into the BOM a recipe generated.

Approving an FM Recipe writes a standard submitted ``BOM`` whose rows carry the
ingredient quantities in the clear. That is what ERPNext needs to run the plant,
and it is also the formula written in another unit, so the recipe's ``permlevel``
stops at the edge of it.

What is closed here is the bulk: list and report queries, the child rows asked
for directly, and a copy of the document to take away.

What is deliberately **not** closed is ``read`` on the BOM *document*. Costing
is built on it: ``costing.simulator`` gives a caller without recipe access the
totals without the lines, which is what costing is for, so denying document read
would take the cost screen away from the people it was written for. See the
module docstring of :mod:`food_manufacturing.recipe_access` for why the
field-level answers - a permlevel, or v16's ``mask`` - are worse than this one.

One consequence is deliberate and worth knowing: a Desk user without recipe
access no longer sees recipe-generated BOMs in the BOM list or in a BOM link
field, so they cannot pick one when planning a Work Order. Planning a run of a
confidential recipe is a recipe-level act, and the alternative was leaving the
formula one ``/api/resource`` call away from every console operator.

Registered through ``has_permission`` and ``permission_query_conditions`` in
hooks.py; BOM belongs to ERPNext, so nothing here edits that app.
"""

import frappe

from food_manufacturing.recipe_access import has_formula_access

#: Rights that take a copy of the document away with them.
EXTRACTING_RIGHTS = ("print", "email", "export")


def has_permission(doc, ptype=None, user=None) -> bool:
	"""Refuse to print, email or export a BOM carrying a recipe's formula.

	A controller ``has_permission`` hook can only ever deny, never grant, so
	returning True leaves ERPNext's own rules in charge of everything else -
	``read`` included.
	"""
	if ptype not in EXTRACTING_RIGHTS:
		return True

	if not doc.get("fm_recipe"):
		return True

	return has_formula_access(user)


def get_permission_query_conditions(user=None, doctype=None) -> str:
	"""Keep recipe-generated BOMs out of list and report queries.

	This is also what closes ``/api/resource/BOM Item?parent=BOM``, which is the
	cheap bulk route to the lines - every recipe's quantities in one request.
	v16 answers a child-table query by joining the parent and applying *the
	parent's* conditions (``frappe.database.query.Engine.add_permission_conditions``),
	so a condition registered on BOM Item would never be consulted and this one
	covers both routes.

	Queries that run with ``ignore_permissions`` are untouched, which is how both
	ERPNext and this app read their own child rows (``frappe.get_all``), so no
	manufacturing arithmetic changes.
	"""
	if has_formula_access(user):
		return ""

	# coalesce rather than ifnull: this has to hold on Postgres too.
	return "coalesce(`tabBOM`.fm_recipe, '') = ''"

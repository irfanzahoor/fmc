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

What this does not reach
------------------------
Approving a recipe generates a standard submitted ``BOM``, and ERPNext grants
``read`` on BOM to **Manufacturing User** - a role every console operator needs
for the production screen. Reading that BOM as a document therefore still shows
``items[].qty``, and a Work Order against it still shows ``required_qty``.

That is a provisioning fact rather than an oversight, because neither framework
answer survives contact with ERPNext:

* a ``permlevel`` on ``BOM Item.qty`` applies site-wide and is reset on write,
  so nobody without level 1 could save a BOM at all; and
* v16's ``mask`` is applied in ``db_query`` *after* the permission check, so it
  reaches ``frappe.get_all`` too - it would feed ``"XXXXXXXX"`` into ERPNext's
  own manufacturing arithmetic.

What **is** closed is every route that would hand out those rows in bulk or as a
document to take away - see :mod:`food_manufacturing.overrides.bom` - and the
real control is which accounts are given BOM read at all. ``docs/workflows.md``
says the same thing where it lists the roles a console user needs.
"""

import frappe

#: The ``permlevel`` the FM Recipe ingredient lines sit at.
FORMULA_PERMLEVEL = 1


def has_formula_access(user: str | None = None) -> bool:
	"""Whether ``user`` reads FM Recipe at the confidential permlevel.

	Asked of the recipe's own meta so there is no second rule to keep in step
	with the DocType's permissions.
	"""
	access = frappe.get_meta("FM Recipe").get_permlevel_access("read", user=user)
	return FORMULA_PERMLEVEL in access


def formula_boms(boms) -> set:
	"""Which of ``boms`` an FM Recipe generated, in one query.

	A BOM that no FM Recipe generated is ordinary ERPNext data and is not gated
	here - this app does not decide who reads other people's BOMs.

	The marker is the BOM's own ``fm_recipe``, which recipe approval writes, and
	not a lookup from the FM Recipe side. Both identify the same BOMs, but only
	one of them can also be expressed as the SQL that
	:func:`food_manufacturing.overrides.bom.get_permission_query_conditions`
	needs - and two markers for one question is how the form rule and the query
	rule drift apart.

	A cancelled recipe is still gated: its BOM came from a formula, and
	cancelling the paperwork does not make the quantities public.
	"""
	codes = {bom for bom in (boms or []) if bom}
	if not codes:
		return set()

	return set(
		frappe.get_all(
			"BOM",
			filters={"name": ("in", list(codes)), "fm_recipe": ("is", "set")},
			pluck="name",
			order_by="name asc",
		)
	)


def may_see_formulas(boms, user: str | None = None) -> dict:
	"""Map bom -> whether ``user`` may see its per-ingredient lines.

	Answers for a whole set in one query, because the callers that need this ask
	about every run on a screen and a question per run is a query per run.
	"""
	codes = {bom for bom in (boms or []) if bom}
	if not codes:
		return {}

	gated = formula_boms(codes)
	if not gated:
		return dict.fromkeys(codes, True)

	# The permlevel is only read once the answer can depend on it.
	allowed = has_formula_access(user)

	return {bom: allowed or bom not in gated for bom in codes}


def may_see_formula(bom: str | None, user: str | None = None) -> bool:
	"""Whether this user may see the per-ingredient lines behind ``bom``."""
	if not bom:
		return True

	return may_see_formulas([bom], user=user).get(bom, True)

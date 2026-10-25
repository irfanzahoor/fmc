"""Serial and Batch Bundle compatibility.

v16 denormalised several columns onto the ``Serial and Batch Entry`` child row
which v15 keeps only on the parent ``Serial and Batch Bundle``:

=========================  =====  =====
Column on the child row      v15    v16
=========================  =====  =====
``batch_no``                 yes    yes
``warehouse``                yes    yes
``qty``                      yes    yes
``is_outward``               yes    yes
``is_cancelled``             no     yes
``item_code``                no     yes
``voucher_no``/``_type``     no     yes
=========================  =====  =====

A bundle holds one item and is cancelled as a whole, so on v15 those facts are
read from the parent instead. :func:`get_entries` and :func:`restrict_to_live`
do that transparently, so callers name the columns they want on either major.

Where the child row already carries the column the work is passed straight
through, so v16 keeps its original single-query behaviour.

Resolution is by schema capability, so a site that backports either column is
handled correctly.
"""

import frappe
from frappe import _
from frappe.utils import cint

from food_manufacturing.compat import meta_has_field

ENTRY_DOCTYPE = "Serial and Batch Entry"
BUNDLE_DOCTYPE = "Serial and Batch Bundle"

#: Columns v16 carries on the child row but v15 keeps only on the parent bundle.
PARENT_BACKED_COLUMNS = (
	"is_cancelled",
	"item_code",
	"voucher_no",
	"voucher_type",
	"type_of_transaction",
)


def entry_has_column(fieldname: str) -> bool:
	"""True when the child row itself carries ``fieldname``."""
	return meta_has_field(ENTRY_DOCTYPE, fieldname)


def _parent_backed(names) -> set:
	"""Of ``names``, those this version must read from the parent bundle."""
	return {n for n in names if n in PARENT_BACKED_COLUMNS and not entry_has_column(n)}


def _equals(actual, expected) -> bool:
	"""Compare a bundle value with a filter value.

	A Check column arrives as 0/1 but may read back as None, so numeric
	comparisons go through ``cint``; anything else is compared as given, which
	keeps a string filter such as ``item_code`` from matching on ``cint``
	collapsing every non-numeric value to 0.
	"""
	if isinstance(expected, bool | int):
		return cint(actual) == cint(expected)

	return actual == expected


def restrict_to_live(query, entry):
	"""Restrict a query builder query over ``entry`` to rows of live bundles.

	``entry`` is the ``Serial and Batch Entry`` table in ``query``. Where the
	child row has no ``is_cancelled`` of its own, the parent bundle's is used -
	a bundle is cancelled as a whole, so the two say the same thing.
	"""
	if entry_has_column("is_cancelled"):
		return query.where(entry.is_cancelled == 0)

	bundle = frappe.qb.DocType(BUNDLE_DOCTYPE)
	return query.inner_join(bundle).on(bundle.name == entry.parent).where(bundle.is_cancelled == 0)


def get_entries(filters: dict, fields=None, order_by: str | None = None, pluck: str | None = None):
	"""``frappe.get_all`` over Serial and Batch Entry, parent columns included.

	``fields``, ``pluck`` and ``filters`` may name any column in
	:data:`PARENT_BACKED_COLUMNS`. On a version that carries them on the child
	row this is one query; otherwise the rows are matched to their parents in a
	second, bounded query - never one query per row.

	Only equality is supported on a parent-backed filter, which is all this app
	needs; anything else would silently return the wrong rows, so it throws.
	"""
	fields = list(fields or [])
	indirect = _parent_backed([*fields, *([pluck] if pluck else []), *filters])

	if not indirect:
		return frappe.get_all(
			ENTRY_DOCTYPE,
			filters=filters,
			fields=fields or None,
			order_by=order_by,
			pluck=pluck,
		)

	parent_filters = {k: v for k, v in filters.items() if k in indirect}
	for key, value in parent_filters.items():
		if isinstance(value, list | tuple):
			frappe.throw(
				_("Only equality is supported on {0} of a Serial and Batch Entry.").format(key)
			)

	# ``parent`` is always selected so the rows can be matched to their bundles,
	# and projected away again below if the caller did not ask for it.
	child_fields = {"parent", *(f for f in [*fields, pluck] if f and f not in indirect)}
	rows = frappe.get_all(
		ENTRY_DOCTYPE,
		filters={k: v for k, v in filters.items() if k not in indirect},
		fields=sorted(child_fields),
		order_by=order_by,
	)
	if not rows:
		return []

	wanted = sorted(indirect)
	bundles = {
		row.name: row
		for row in frappe.get_all(
			BUNDLE_DOCTYPE,
			filters={"name": ("in", sorted({row.parent for row in rows}))},
			fields=["name", *wanted],
			order_by="name asc",
		)
	}

	kept = []
	for row in rows:
		bundle = bundles.get(row.parent)
		if bundle is None:
			continue

		if any(not _equals(bundle.get(k), v) for k, v in parent_filters.items()):
			continue

		for column in wanted:
			row[column] = bundle.get(column)

		kept.append(row)

	if pluck:
		return [row.get(pluck) for row in kept]

	return [frappe._dict({f: row.get(f) for f in fields}) for row in kept] if fields else kept


__all__ = [
	"entry_has_column",
	"get_entries",
	"restrict_to_live",
]

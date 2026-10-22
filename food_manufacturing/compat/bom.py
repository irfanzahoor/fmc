"""BOM by-product compatibility.

ERPNext renamed the BOM by-product table between majors:

===============  =========================  =======================
Version          BOM / Work Order field     Child DocType
===============  =========================  =======================
v15              ``scrap_items``            ``BOM Scrap Item``
v16              ``secondary_items``        ``BOM Secondary Item``
===============  =========================  =======================

``process_loss_percentage`` / ``process_loss_qty`` exist on BOM in both majors
and need no shim; non-recoverable process loss is therefore expressed the same
way on either version. Only the *recoverable* by-product table moved.

Resolution is by schema capability, so a site that backports either name is
handled correctly.
"""

import frappe

from food_manufacturing.compat import meta_has_field

#: Candidate field names, newest naming first.
_BOM_BYPRODUCT_FIELDS = ("secondary_items", "scrap_items")

_BYPRODUCT_CHILD_DOCTYPE = {
	"secondary_items": "BOM Secondary Item",
	"scrap_items": "BOM Scrap Item",
}


def byproduct_field(doctype: str = "BOM") -> str | None:
	"""Return the by-product table fieldname on ``doctype``, or None.

	``doctype`` is ``BOM`` or ``Work Order``. Work Order only grew a
	by-product table in v16, so None is a valid answer there on v15.
	"""
	for fieldname in _BOM_BYPRODUCT_FIELDS:
		if meta_has_field(doctype, fieldname):
			return fieldname

	return None


def byproduct_child_doctype(doctype: str = "BOM") -> str | None:
	"""Return the child DocType backing the by-product table, or None."""
	fieldname = byproduct_field(doctype)
	if not fieldname:
		return None

	# Trust the schema over the table above: a site may have renamed either.
	options = frappe.get_meta(doctype).get_field(fieldname).options
	return options or _BYPRODUCT_CHILD_DOCTYPE.get(fieldname)


def get_byproducts(doc) -> list:
	"""Rows of the by-product table on a BOM or Work Order document.

	Returns an empty list when the version has no such table, so callers can
	iterate unconditionally.
	"""
	fieldname = byproduct_field(doc.doctype)
	if not fieldname:
		return []

	return doc.get(fieldname) or []


def supports_work_order_byproducts() -> bool:
	"""True when Work Order itself carries a by-product table (v16+)."""
	return byproduct_field("Work Order") is not None

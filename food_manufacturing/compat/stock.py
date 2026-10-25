"""Stock Settings compatibility.

v16 introduced a site-wide master switch for lot handling,
``Stock Settings.enable_serial_and_batch_no_for_item`` ("Activate Serial /
Batch No for Item"), and ships ``erpnext/patches/v16_0/enable_serial_batch_setting.py``
to turn it on for upgraded sites. While it is off, v16 refuses to build a
Serial and Batch Bundle, so no batched stock can move.

v15 has no such gate - lot handling is unconditionally available - so there is
nothing to read or write there. Reading reports None and writing is a no-op,
which lets callers set the switch unconditionally on either major.

Resolution is by schema capability, so a site that backports the field is
handled correctly.
"""

import frappe
from frappe.utils import cint

from food_manufacturing.compat import meta_has_field

#: v16 fieldname of the site-wide lot-handling switch.
LOT_FEATURE_FIELD = "enable_serial_and_batch_no_for_item"


def lot_feature_field() -> str | None:
	"""Fieldname of the site-wide lot switch, or None on a version without one."""
	return LOT_FEATURE_FIELD if meta_has_field("Stock Settings", LOT_FEATURE_FIELD) else None


def get_lot_feature() -> int | None:
	"""Current value of the switch, or None where the version has no switch.

	None is the value to hand back to :func:`set_lot_feature` to restore, so
	save/restore pairs stay symmetrical on both majors.
	"""
	fieldname = lot_feature_field()
	if not fieldname:
		return None

	return cint(frappe.db.get_single_value("Stock Settings", fieldname))


def set_lot_feature(value: int | None) -> None:
	"""Set the switch, clearing the Single's document cache.

	A no-op when the version has no such field, or when ``value`` is None -
	the value :func:`get_lot_feature` reports on such a version.
	"""
	fieldname = lot_feature_field()
	if not fieldname or value is None:
		return

	frappe.db.set_single_value("Stock Settings", fieldname, cint(value))
	frappe.clear_document_cache("Stock Settings", "Stock Settings")


__all__ = [
	"get_lot_feature",
	"lot_feature_field",
	"set_lot_feature",
]

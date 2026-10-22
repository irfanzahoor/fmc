"""Version compatibility layer for Frappe/ERPNext v15 and v16.

All version-dependent behaviour lives in this package. Controllers and reports
import from here and never test versions themselves, so a new major version is
absorbed by changing this layer only.

Preference order for deciding behaviour:

1. Schema capability (``frappe.get_meta(...).has_field(...)``) - survives
   backports and point releases.
2. Presence of a DocType or module.
3. Major version number - last resort only.
"""

import frappe
from frappe.utils import cint

__all__ = [
	"erpnext_major",
	"frappe_major",
	"has_doctype",
	"meta_has_field",
]


def frappe_major() -> int:
	"""Major version of the installed Frappe framework."""
	import frappe as _frappe

	return cint(_frappe.__version__.split(".")[0])


def erpnext_major() -> int:
	"""Major version of the installed ERPNext app."""
	import erpnext

	return cint(erpnext.__version__.split(".")[0])


def has_doctype(doctype: str) -> bool:
	"""True when ``doctype`` exists in this site's schema.

	Cached per request by ``frappe.db.exists`` round-trip avoidance - the
	DocType list is small and already cached by the framework.
	"""
	return bool(frappe.db.exists("DocType", doctype))


def meta_has_field(doctype: str, fieldname: str) -> bool:
	"""True when ``doctype`` has ``fieldname``, using the cached meta."""
	return bool(frappe.get_meta(doctype).has_field(fieldname))

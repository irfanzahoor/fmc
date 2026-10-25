"""Holds the Desk's Data Import export to this app's permlevel guarantee.

``frappe.core.doctype.data_import.data_import.download_template`` builds the
framework's own ``Exporter``, which on v15 ignores ``permlevel`` - see
``compat/exporter.py``. Registered in hooks.py under
``override_whitelisted_methods`` so the Desk export dialog, ``/api/method`` and
anything else reaching that endpoint go through the permlevel-aware exporter.

Only this app's own DocTypes are rerouted. Other apps on the site keep the
framework's behaviour exactly, because silently changing how *their* exports
treat permlevel is not this app's call to make.
"""

import frappe
from frappe.core.doctype.data_import.data_import import (
	download_template as _core_download_template,
)

from food_manufacturing.compat.exporter import Exporter

APP_NAME = "food_manufacturing"


def _is_ours(doctype: str) -> bool:
	"""True when ``doctype`` belongs to one of this app's modules."""
	module = frappe.get_cached_value("DocType", doctype, "module")
	return bool(module) and module in set(frappe.get_module_list(APP_NAME))


@frappe.whitelist()
def download_template(
	doctype: str,
	export_fields=None,
	export_records: str | None = None,
	export_filters=None,
	file_type: str = "CSV",
):
	"""``download_template``, with permlevel enforced for our own DocTypes."""
	if not _is_ours(doctype):
		return _core_download_template(
			doctype=doctype,
			export_fields=export_fields,
			export_records=export_records,
			export_filters=export_filters,
			file_type=file_type,
		)

	# Mirrors the core entry point, differing only in the Exporter class used.
	frappe.has_permission(doctype, "read", throw=True)

	Exporter(
		doctype,
		export_fields=frappe.parse_json(export_fields),
		export_data=export_records != "blank_template",
		export_filters=frappe.parse_json(export_filters),
		file_type=file_type,
		export_page_length=5 if export_records == "5_records" else None,
	).build_response()

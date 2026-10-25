"""Data Import exporter compatibility.

v16's ``Exporter`` runs every requested field through
``frappe.model.get_permitted_fields``, so a ``permlevel`` 1 field never reaches
a CSV for a user who holds permlevel 0 access only. v15's ``Exporter`` filters
on fieldtype alone and will happily export a permlevel 1 field to anyone allowed
to read the DocType at all:

===============  ==================================================
Version          ``Exporter`` honours ``permlevel``
===============  ==================================================
v15              no
v16              yes
===============  ==================================================

This app protects confidential recipe data with ``permlevel``, and that
protection has to hold on exports as much as on forms, APIs and reports. So the
check is applied here rather than left to the framework version.

Filtering is **idempotent** - dropping a field the core exporter would have
dropped anyway costs nothing - so this subclass is used unconditionally and
there is no version branch to keep in step.
"""

import frappe
from frappe.core.doctype.data_import.exporter import Exporter as _CoreExporter
from frappe.model import get_permitted_fields


class Exporter(_CoreExporter):
	"""``Exporter`` that never emits a field above the user's permlevel access."""

	def get_exportable_fields(self, doctype, fieldnames):
		# ``parenttype`` is what lets a child table's permissions be read off
		# the parent DocType, the same way the v16 exporter resolves them.
		permitted = set(
			get_permitted_fields(
				doctype,
				parenttype=self.doctype if frappe.get_meta(doctype).istable else None,
			)
		)

		return super().get_exportable_fields(doctype, [f for f in fieldnames if f in permitted])


__all__ = ["Exporter"]

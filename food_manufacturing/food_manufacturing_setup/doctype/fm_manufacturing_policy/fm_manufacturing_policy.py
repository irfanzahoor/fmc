from marshal import version

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

#: Policy warehouse fields, in the order they appear on the form.
WAREHOUSE_FIELDS = (
	"quarantine_warehouse",
	"rejected_warehouse",
	"bulk_warehouse",
	"packaging_warehouse",
	"finished_goods_warehouse",
)

#: Warehouses that must never point at the same record as each other.
DISTINCT_WAREHOUSE_FIELDS = (
	"quarantine_warehouse",
	"rejected_warehouse",
	"bulk_warehouse",
	"finished_goods_warehouse",
)


class FMManufacturingPolicy(Document):
	def validate(self):
		self.validate_warehouse_company()
		self.validate_distinct_warehouses()
		self.validate_percentages()
		self.validate_alert_days()

	def on_update(self):
		# Policy is read on nearly every stock and production validation.
		frappe.clear_document_cache(self.doctype, self.name)

	def validate_warehouse_company(self):
		"""Every configured warehouse must belong to this policy's company."""
		warehouses = [self.get(fieldname) for fieldname in WAREHOUSE_FIELDS]
		warehouses = [w for w in warehouses if w]
		if not warehouses:
			return

		# One query for every warehouse rather than one per field.
		company_by_warehouse = dict(
			frappe.get_all(
				"Warehouse",
				filters={"name": ("in", warehouses)},
				fields=["name", "company"],
				as_list=True,
			)
		)

		for fieldname in WAREHOUSE_FIELDS:
			warehouse = self.get(fieldname)
			if not warehouse:
				continue

			warehouse_company = company_by_warehouse.get(warehouse)
			if warehouse_company and warehouse_company != self.company:
				frappe.throw(
					_("{0} {1} belongs to company {2}, not {3}.").format(
						_(self.meta.get_label(fieldname)),
						frappe.bold(warehouse),
						frappe.bold(warehouse_company),
						frappe.bold(self.company),
					),
					title=_("Company Mismatch"),
				)

	def validate_distinct_warehouses(self):
		"""Quarantine, rejected, bulk and finished stock must be separable."""
		seen = {}
		for fieldname in DISTINCT_WAREHOUSE_FIELDS:
			warehouse = self.get(fieldname)
			if not warehouse:
				continue

			if warehouse in seen:
				frappe.throw(
					_("{0} and {1} cannot be the same warehouse {2}.").format(
						_(self.meta.get_label(seen[warehouse])),
						_(self.meta.get_label(fieldname)),
						frappe.bold(warehouse),
					),
					title=_("Warehouse Conflict"),
				)

			seen[warehouse] = fieldname

	def validate_percentages(self):
		for fieldname in ("min_remaining_shelf_life_percent", "yield_variance_tolerance_percent"):
			value = flt(self.get(fieldname))
			if value < 0 or value > 100:
				frappe.throw(
					_("{0} must be between 0 and 100.").format(_(self.meta.get_label(fieldname))),
					title=_("Invalid Percentage"),
				)

	def validate_alert_days(self):
		if cint(self.near_expiry_alert_days) < 0:
			frappe.throw(
				_("{0} cannot be negative.").format(_(self.meta.get_label("near_expiry_alert_days"))),
				title=_("Invalid Value"),
			)


def get_policy(company: str):
	"""Return the cached policy document for ``company``.

	Raises if no policy exists: the policy carries the quarantine and rejected
	warehouses, so silently defaulting would let unreleased material flow into
	production. Callers that must tolerate an unconfigured company should use
	:func:`get_policy_if_any`.
	"""
	policy = get_policy_if_any(company)
	if not policy:
		frappe.throw(
			_("No FM Manufacturing Policy is configured for company {0}.").format(frappe.bold(company)),
			title=_("Policy Missing"),
		)

	return policy


def get_policy_if_any(company: str):
	"""Return the cached enabled policy for ``company``, or None."""
	if not company:
		return None

	if not frappe.db.exists("FM Manufacturing Policy", company):
		return None

	policy = frappe.get_cached_doc("FM Manufacturing Policy", company)
	return policy if cint(policy.enabled) else None
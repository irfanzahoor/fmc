"""Company fixtures restricted to the disposable CI site, never shared sites."""

import frappe
from frappe import _


def prepare():
	if frappe.local.site != "ci.localhost" or not frappe.conf.get("fm_isolated_test_site"):
		frappe.throw(_("CI fixtures require the disposable ci.localhost site."))
	for label, abbreviation in (("FM CI Primary", "FCP"), ("FM CI Secondary", "FCS")):
		if not frappe.db.exists("Company", label):
			frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": label,
					"abbr": abbreviation,
					"default_currency": "PKR",
					"country": "Pakistan",
					"chart_of_accounts": "Standard",
				}
			).insert()

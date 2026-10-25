"""Company fixtures restricted to disposable test sites, never shared sites."""

import frappe
from frappe import _

#: Site config flag a site must carry before it may be given fixture companies.
ISOLATION_FLAG = "fm_isolated_test_site"

#: Fixture parties, so dispatch and receiving have a counterparty to transact with.
CUSTOMER = "FM CI Customer"
SUPPLIER = "FM CI Supplier"


def prepare():
	"""Create the two fixture companies on a site flagged as disposable.

	Creating a Company builds a full chart of accounts and is effectively
	irreversible, so this refuses to run on any site that has not explicitly
	opted in. The gate is the :data:`ISOLATION_FLAG` key in site config rather
	than a hardcoded site name, so every disposable site - ``ci.localhost`` in
	CI, a local version-validation site - can carry the fixtures while a shared
	or production site still cannot.
	"""
	if not frappe.conf.get(ISOLATION_FLAG):
		frappe.throw(
			_("CI fixtures require a disposable site with {0} set in its site config.").format(
				frappe.bold(ISOLATION_FLAG)
			)
		)
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

	_ensure_parties()


def _ensure_parties() -> None:
	"""A counterparty each for the dispatch and receiving tests.

	Unlike a Company, a Customer or Supplier is cheap and genuinely removable,
	so these are created rather than only discovered. The tests pick up whatever
	party the site already has, so on a populated site this adds nothing they
	need - it exists for a site that starts empty.
	"""
	if not frappe.db.exists("Customer", CUSTOMER):
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": CUSTOMER,
				"customer_group": frappe.db.get_value(
					"Customer Group", {"is_group": 0}, "name", order_by="name asc"
				),
				"territory": frappe.db.get_value(
					"Territory", {"is_group": 0}, "name", order_by="name asc"
				),
			}
		).insert()

	if not frappe.db.exists("Supplier", SUPPLIER):
		frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": SUPPLIER,
				"supplier_group": frappe.db.get_value(
					"Supplier Group", {"is_group": 0}, "name", order_by="name asc"
				),
			}
		).insert()

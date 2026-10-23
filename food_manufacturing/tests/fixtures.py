"""Shared test fixtures.

These deliberately never create a Company or a Warehouse. Creating a Company
builds a full chart of accounts and is effectively irreversible, which is unsafe
on a shared or populated site. Instead we discover what the site already has and
skip when it cannot supply what a test needs.

Items and Batches *are* created, because they are cheap, scoped by an `_FMT`
name prefix, and removed again in teardown.
"""

import unittest

import frappe

PREFIX = "_FMT"
MIN_WAREHOUSES = 3


def discover_site():
	"""Return a dict of usable company/warehouse fixtures, or None."""
	companies = frappe.get_all("Company", pluck="name", order_by="name")
	if len(companies) < 2:
		return None

	# A disabled warehouse cannot take a transaction, so it must never be
	# chosen as a fixture - the site may hold retired warehouses alongside
	# live ones.
	rows = frappe.get_all(
		"Warehouse",
		filters={"company": ("in", companies), "is_group": 0, "disabled": 0},
		fields=["name", "company"],
		order_by="company asc, name asc",
	)

	by_company = {}
	for row in rows:
		by_company.setdefault(row.company, []).append(row.name)

	primary = next((c for c in companies if len(by_company.get(c, [])) >= MIN_WAREHOUSES), None)
	if not primary:
		return None

	foreign = next((c for c in companies if c != primary and by_company.get(c)), None)
	if not foreign:
		return None

	warehouses = by_company[primary]
	return {
		"company": primary,
		"quarantine": warehouses[0],
		"rejected": warehouses[1],
		"stores": warehouses[2],
		"foreign_company": foreign,
		"foreign_warehouse": by_company[foreign][0],
	}


def require_site():
	site = discover_site()
	if not site:
		raise unittest.SkipTest(
			f"Site needs two companies, one with at least {MIN_WAREHOUSES} leaf warehouses"
		)

	return site


def ensure_policy(site, **overrides):
	"""Create (or replace) the policy for the discovered company."""
	frappe.db.delete("FM Manufacturing Policy", {"company": site["company"]})

	values = {
		"doctype": "FM Manufacturing Policy",
		"company": site["company"],
		"quarantine_warehouse": site["quarantine"],
		"rejected_warehouse": site["rejected"],
	}
	values.update(overrides)

	policy = frappe.get_doc(values)
	policy.insert()
	return policy


def ensure_item(suffix: str, nature: str | None = None, has_batch: bool = True,
                uom: str | None = None) -> str:
	"""Create a stock item scoped to the test prefix.

	``has_batch`` is False for packaging materials, which are counted rather
	than lot-tracked.
	"""
	item_code = f"{PREFIX} {suffix}"
	if not frappe.db.exists("Item", item_code):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
				"stock_uom": uom or ("Kg" if frappe.db.exists("UOM", "Kg") else "Nos"),
				"is_stock_item": 1,
				"has_batch_no": 1 if has_batch else 0,
				"create_new_batch": 1 if has_batch else 0,
				"batch_number_series": f"{PREFIX}-{suffix.replace(' ', '')}-.###" if has_batch else None,
				"fm_material_nature": nature,
			}
		).insert()
	elif nature is not None:
		frappe.db.set_value("Item", item_code, "fm_material_nature", nature)

	return item_code


def ensure_batch(item_code: str, suffix: str, status: str | None = None) -> str:
	"""Create a Batch with an explicit quality status."""
	batch_id = f"{PREFIX}-{suffix}"
	if not frappe.db.exists("Batch", batch_id):
		batch = frappe.get_doc(
			{
				"doctype": "Batch",
				"batch_id": batch_id,
				"item": item_code,
			}
		)
		batch.insert()

	# Written directly because the field is read-only by design - only
	# FM Batch Release may set it through the UI.
	frappe.db.set_value("Batch", batch_id, "fm_quality_status", status)
	frappe.clear_document_cache("Batch", batch_id)
	return batch_id


def cleanup():
	"""Remove everything this test prefix created."""
	frappe.db.delete("FM Batch Release", {"batch": ("like", f"{PREFIX}-%")})
	frappe.db.delete("Batch", {"name": ("like", f"{PREFIX}-%")})
	frappe.db.delete("Item", {"name": ("like", f"{PREFIX} %")})


def ensure_user(suffix: str, roles: tuple, user_type: str = "System User") -> str:
	"""Create a scoped test user with exactly ``roles``."""
	email = f"{PREFIX.lower()}.{suffix}@example.com"
	if not frappe.db.exists("User", email):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": f"{PREFIX} {suffix}",
				"send_welcome_email": 0,
				"user_type": user_type,
			}
		)
		user.insert(ignore_permissions=True)  # test bootstrap
	else:
		user = frappe.get_doc("User", email)

	user.user_type = user_type
	user.set("roles", [])
	for role in roles:
		user.append("roles", {"role": role})
	user.save(ignore_permissions=True)  # test bootstrap

	return email


def restrict_user_to_company(email: str, company: str) -> None:
	"""Apply a standard User Permission so the user sees one company only."""
	frappe.db.delete("User Permission", {"user": email, "allow": "Company"})
	frappe.get_doc(
		{
			"doctype": "User Permission",
			"user": email,
			"allow": "Company",
			"for_value": company,
			"apply_to_all_doctypes": 1,
		}
	).insert(ignore_permissions=True)  # test bootstrap
	frappe.clear_cache(user=email)


def ensure_level0_role(doctype: str, role_suffix: str, **perms) -> str:
	"""A throwaway role with permlevel-0 rights only, for permlevel tests.

	Lets a test prove that a user who may legitimately read, write or export a
	document still cannot reach its permlevel-1 fields.
	"""
	from frappe.permissions import add_permission, update_permission_property

	role = f"{PREFIX} {role_suffix}"
	if not frappe.db.exists("Role", role):
		frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
			ignore_permissions=True
		)  # test bootstrap

	add_permission(doctype, role, 0)
	for ptype, value in perms.items():
		update_permission_property(doctype, role, 0, ptype, value)

	frappe.clear_cache()
	return role


def cleanup_test_roles():
	frappe.db.delete("Custom DocPerm", {"role": ("like", f"{PREFIX}%")})
	frappe.db.delete("Has Role", {"role": ("like", f"{PREFIX}%")})
	frappe.db.delete("Role", {"name": ("like", f"{PREFIX}%")})
	frappe.clear_cache()


def cleanup_users():
	emails = frappe.get_all("User", filters={"email": ("like", f"{PREFIX.lower()}.%")}, pluck="name")
	if not emails:
		return

	frappe.db.delete("User Permission", {"user": ("in", emails)})
	frappe.db.delete("Has Role", {"parent": ("in", emails)})
	frappe.db.delete("User", {"name": ("in", emails)})
	for email in emails:
		frappe.clear_cache(user=email)


def ensure_uom(name: str) -> str:
	if not frappe.db.exists("UOM", name):
		frappe.get_doc({"doctype": "UOM", "uom_name": name}).insert(ignore_permissions=True)
	return name


def ensure_uom_conversion(from_uom: str, to_uom: str, value: float) -> None:
	"""Global UOM Conversion Factor, e.g. 1 Kg -> 1000 Gram."""
	if frappe.db.exists("UOM Conversion Factor", {"from_uom": from_uom, "to_uom": to_uom}):
		return

	frappe.get_doc(
		{
			"doctype": "UOM Conversion Factor",
			"from_uom": from_uom,
			"to_uom": to_uom,
			"value": value,
		}
	).insert(ignore_permissions=True)


def cleanup_requests():
	"""Remove Material Requests this app's tests proposed.

	A draft can be deleted outright; a submitted one has to be cancelled first,
	or its reservations would outlive the test and skew the next plan.
	"""
	names = frappe.get_all(
		"Material Request",
		filters={"fm_operation_key": ("is", "set")},
		fields=["name", "docstatus"],
	)
	for row in names:
		if row.docstatus == 1:
			frappe.get_doc("Material Request", row.name).cancel()
		frappe.delete_doc("Material Request", row.name, force=True, ignore_permissions=True)


def cleanup_recipes():
	recipes = frappe.get_all("FM Recipe", filters={"item": ("like", f"{PREFIX}%")}, pluck="name")
	boms = frappe.get_all("BOM", filters={"item": ("like", f"{PREFIX}%")}, pluck="name")

	frappe.db.delete("Work Order", {"production_item": ("like", f"{PREFIX}%")})
	if boms:
		frappe.db.delete("BOM Item", {"parent": ("in", boms)})
		frappe.db.delete("BOM Explosion Item", {"parent": ("in", boms)})
		frappe.db.delete("BOM", {"name": ("in", boms)})
	if recipes:
		frappe.db.delete("FM Recipe Ingredient", {"parent": ("in", recipes)})
		frappe.db.delete("FM Recipe", {"name": ("in", recipes)})

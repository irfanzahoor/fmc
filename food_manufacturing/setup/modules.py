"""Module Def bootstrap.

Frappe scans for DocType JSON before it creates the Module Def records declared
in ``modules.txt``, so the first ``bench migrate`` after a new module is added
silently skips that module's DocTypes and only the *second* migrate picks them
up. Creating the Module Defs in ``before_install`` and in a ``pre_model_sync``
patch makes a single migrate sufficient.
"""

import frappe

APP_NAME = "food_manufacturing"


def ensure_module_defs() -> None:
	"""Create any Module Def declared in modules.txt. Safe to run repeatedly."""
	module_names = frappe.get_module_list(APP_NAME)
	if not module_names:
		return

	existing = set(
		frappe.get_all(
			"Module Def",
			filters={"name": ("in", module_names)},
			pluck="name",
			order_by="name asc",
		)
	)

	for module_name in module_names:
		if module_name in existing:
			continue

		module_def = frappe.new_doc("Module Def")
		module_def.module_name = module_name
		module_def.app_name = APP_NAME
		module_def.insert(ignore_permissions=True)  # install-time bootstrap, no session user

	frappe.clear_cache()


def sync_child_doctypes() -> None:
	"""Import this app's child-table DocTypes before the main sync pass.

	Frappe hardcodes a dependency order for its own DocTypes but syncs every
	other app by walking the module folders, so a parent DocType can be synced
	before the child table its Table field points at. When that happens the
	parent fails validation and ``bench migrate`` swallows the error, leaving
	the DocType missing - which is how ``FM Recipe`` silently failed to install
	while ``FM Recipe Ingredient`` succeeded (the parent sorts first
	alphabetically).

	Importing the ``istable`` DocTypes up front removes the dependence on folder
	ordering. It is idempotent and only touches a handful of small files.
	"""
	import json
	import os

	from frappe.modules.import_file import import_file_by_path

	app_path = frappe.get_app_path(APP_NAME)

	for module_name in frappe.get_module_list(APP_NAME):
		module_dir = os.path.join(app_path, frappe.scrub(module_name), "doctype")
		if not os.path.isdir(module_dir):
			continue

		for doctype_dir in sorted(os.listdir(module_dir)):
			path = os.path.join(module_dir, doctype_dir, f"{doctype_dir}.json")
			if not os.path.isfile(path):
				continue

			with open(path) as handle:
				try:
					schema = json.load(handle)
				except ValueError:
					# Let the normal sync pass report a malformed file.
					continue

			if schema.get("istable"):
				import_file_by_path(path, force=False, reset_permissions=False)

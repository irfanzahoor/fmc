"""Role definitions and idempotent creation.

Roles are created before DocType sync (``before_install``) and re-asserted by a
``pre_model_sync`` patch, so a DocType JSON may safely reference them.
"""

import frappe

#: Role name -> flags. ``desk_access`` 1 for operational roles.
FM_ROLES = {
	# Reads and approves confidential formulas. Gates recipe permlevel 1.
	"FM Recipe Manager": {"desk_access": 1},
	# Plans and closes production and packaging runs.
	"FM Production Manager": {"desk_access": 1},
	# Executes runs and records actual consumption on the shop floor.
	"FM Production Operator": {"desk_access": 1},
	# Records inspection results; cannot release.
	"FM Quality Inspector": {"desk_access": 1},
	# Authorised to hold, release and reject batches.
	"FM Quality Manager": {"desk_access": 1},
	# Receives, moves and dispatches stock.
	"FM Warehouse Operator": {"desk_access": 1},
}


def ensure_roles() -> None:
	"""Create any missing FM role. Safe to run repeatedly."""
	existing = set(
		frappe.get_all(
			"Role",
			filters={"name": ("in", list(FM_ROLES))},
			pluck="name",
			order_by="name asc",
		)
	)

	for role_name, flags in FM_ROLES.items():
		if role_name in existing:
			continue

		role = frappe.new_doc("Role")
		role.role_name = role_name
		role.desk_access = flags["desk_access"]
		role.insert(ignore_permissions=True)  # install-time bootstrap, no session user

	frappe.clear_cache()

"""Install and migrate entry points.

Every step is idempotent: re-running ``bench install-app`` on a site that
already has the app, or ``bench migrate`` repeatedly, must not duplicate
records or raise.
"""

from food_manufacturing.setup.custom_fields import create_fm_custom_fields
from food_manufacturing.setup.modules import ensure_module_defs, sync_child_doctypes
from food_manufacturing.setup.roles import ensure_roles


def before_install() -> None:
	"""Runs before this app's DocTypes are synced."""
	ensure_module_defs()
	ensure_roles()
	sync_child_doctypes()


def after_install() -> None:
	"""Runs after this app's DocTypes are synced."""
	ensure_roles()
	create_fm_custom_fields()


def after_migrate() -> None:
	"""Runs at the end of every ``bench migrate``."""
	ensure_roles()
	create_fm_custom_fields()

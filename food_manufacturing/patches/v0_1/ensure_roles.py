"""Create FM roles before model sync so DocType permissions resolve."""

from food_manufacturing.setup.roles import ensure_roles


def execute() -> None:
	ensure_roles()

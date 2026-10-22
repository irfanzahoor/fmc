"""Create this app's custom fields on existing installs."""

from food_manufacturing.setup.custom_fields import create_fm_custom_fields


def execute() -> None:
	create_fm_custom_fields()

"""Add transactional operator retry metadata to standard stock documents."""

from food_manufacturing.setup.custom_fields import create_fm_custom_fields


def execute():
	create_fm_custom_fields()

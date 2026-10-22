"""Create Module Defs and child tables before model sync.

Both must exist before the main DocType sync pass, or DocTypes belonging to a
new module - or parents referencing a child table that sorts after them - are
silently skipped. See ``setup/modules.py`` for the detail.
"""

from food_manufacturing.setup.modules import ensure_module_defs, sync_child_doctypes


def execute() -> None:
	ensure_module_defs()
	sync_child_doctypes()

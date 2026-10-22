"""The formula must stay confidential on every read path, not just the form.

`permlevel` 1 on the `ingredients` table and on every child field is the
mechanism. Frappe applies it in three different places, so each is tested
separately:

* ``apply_fieldlevel_read_permissions`` - document reads, used by the form and
  by ``/api/resource/<dt>/<name>`` and ``frappe.client.get``.
* ``get_permitted_fields`` via ``db_query`` - list view, report view, and
  ``frappe.get_list``.
* ``core.doctype.data_import.exporter`` - the Export / data-import template.

A test that only checked the form would prove nothing about the other two.
"""

import frappe

from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.tests import fixtures

CONFIDENTIAL_PARENT_FIELDS = ("ingredients", "total_percentage")
CONFIDENTIAL_CHILD_FIELDS = ("item_code", "percentage", "qty", "stock_qty")


class TestRecipeConfidentiality(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		cls.kg = fixtures.ensure_uom("Kg")

	def setUp(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		fixtures.cleanup_users()
		fixtures.cleanup_test_roles()

		self.blend = fixtures.ensure_item("Secret Blend", nature="Bulk Blend")
		self.chilli = fixtures.ensure_item("Chilli Powder", nature="Raw Material")
		self.cumin = fixtures.ensure_item("Cumin Powder", nature="Raw Material")

		self.recipe = frappe.get_doc(
			{
				"doctype": "FM Recipe",
				"item": self.blend,
				"company": self.site["company"],
				"batch_size": 100,
				"batch_uom": self.kg,
				"ingredients": [
					{"item_code": self.chilli, "percentage": 60, "uom": self.kg},
					{"item_code": self.cumin, "percentage": 40, "uom": self.kg},
				],
			}
		)
		self.recipe.insert()

		self.outsider = fixtures.ensure_user("prodmgr", ("FM Production Manager",))
		self.insider = fixtures.ensure_user("recipemgr", ("FM Recipe Manager",))

	def tearDown(self):
		frappe.set_user("Administrator")
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		fixtures.cleanup_users()
		fixtures.cleanup_test_roles()

	# -- path 1: document read ------------------------------------------------

	def test_document_read_hides_the_formula_from_an_outsider(self):
		frappe.set_user(self.outsider)
		doc = frappe.get_doc("FM Recipe", self.recipe.name)
		doc.apply_fieldlevel_read_permissions()

		for fieldname in CONFIDENTIAL_PARENT_FIELDS:
			self.assertFalse(
				getattr(doc, fieldname, None),
				msg=f"{fieldname} leaked to a user without FM Recipe Manager",
			)

	def test_document_read_shows_the_formula_to_the_recipe_manager(self):
		frappe.set_user(self.insider)
		doc = frappe.get_doc("FM Recipe", self.recipe.name)
		doc.apply_fieldlevel_read_permissions()

		self.assertEqual(len(doc.ingredients), 2)
		for row in doc.ingredients:
			self.assertTrue(row.percentage)

	def test_outsider_can_still_read_the_non_confidential_header(self):
		"""Production needs to know a recipe exists, not what is in it."""
		frappe.set_user(self.outsider)
		doc = frappe.get_doc("FM Recipe", self.recipe.name)
		doc.apply_fieldlevel_read_permissions()

		self.assertEqual(doc.item, self.blend)
		self.assertEqual(doc.company, self.site["company"])
		self.assertEqual(doc.status, "Draft")

	# -- path 2: list / report query -----------------------------------------

	def test_permitted_fieldnames_exclude_the_formula_for_an_outsider(self):
		from frappe.model import get_permitted_fields

		frappe.set_user(self.outsider)
		permitted = set(get_permitted_fields("FM Recipe"))
		for fieldname in CONFIDENTIAL_PARENT_FIELDS:
			self.assertNotIn(fieldname, permitted)

		# ...and the child table's own fields
		permitted_child = set(get_permitted_fields("FM Recipe Ingredient", parenttype="FM Recipe"))
		for fieldname in CONFIDENTIAL_CHILD_FIELDS:
			self.assertNotIn(fieldname, permitted_child)

	def test_permitted_fieldnames_include_the_formula_for_the_recipe_manager(self):
		from frappe.model import get_permitted_fields

		frappe.set_user(self.insider)
		permitted = set(get_permitted_fields("FM Recipe"))
		self.assertIn("total_percentage", permitted)

		permitted_child = set(get_permitted_fields("FM Recipe Ingredient", parenttype="FM Recipe"))
		for fieldname in CONFIDENTIAL_CHILD_FIELDS:
			self.assertIn(fieldname, permitted_child)

	def test_get_list_strips_a_confidential_parent_field(self):
		"""db_query drops the column silently rather than raising.

		Asserting on absence is the guarantee that matters: whatever the error
		behaviour, the value must not come back.
		"""
		frappe.set_user(self.outsider)
		rows = frappe.get_list(
			"FM Recipe",
			filters={"name": self.recipe.name},
			fields=["name", "total_percentage"],
			limit=1,
		)
		self.assertEqual(len(rows), 1)
		self.assertNotIn("total_percentage", rows[0])

	def test_get_list_strips_child_percentages(self):
		frappe.set_user(self.outsider)
		rows = frappe.get_list(
			"FM Recipe",
			filters={"name": self.recipe.name},
			fields=["name", "`tabFM Recipe Ingredient`.percentage"],
			limit=1,
		)
		self.assertEqual(len(rows), 1)
		self.assertNotIn("percentage", rows[0])

	def test_get_list_on_the_child_table_strips_percentages(self):
		"""Querying the child DocType directly must not be a way round it."""
		frappe.set_user(self.outsider)
		rows = frappe.get_list(
			"FM Recipe Ingredient",
			filters={"parent": self.recipe.name},
			fields=["name", "percentage", "item_code"],
			parent_doctype="FM Recipe",
			limit=5,
		)
		for row in rows:
			self.assertNotIn("percentage", row)
			self.assertNotIn("item_code", row)

	def test_get_list_returns_the_formula_to_the_recipe_manager(self):
		frappe.set_user(self.insider)
		rows = frappe.get_list(
			"FM Recipe",
			filters={"name": self.recipe.name},
			fields=["name", "total_percentage"],
			limit=1,
		)
		self.assertEqual(len(rows), 1)
		self.assertIn("total_percentage", rows[0])

	# -- path 3: export -------------------------------------------------------

	def exported_fieldnames(self):  # noqa: D401
		"""Fieldnames an explicit export request actually yields.

		The request deliberately asks for the confidential fields, so this
		asks the question that matters: can a user get the formula out by
		requesting it in an export?
		"""
		from frappe.core.doctype.data_import.exporter import Exporter

		exporter = Exporter(
			"FM Recipe",
			export_fields={
				"FM Recipe": ["name", "item", "batch_size", "total_percentage"],
				"ingredients": ["item_code", "percentage", "qty", "stock_qty"],
			},
			export_data=True,
			export_filters={"name": self.recipe.name},
		)
		return {df.fieldname for df in exporter.fields}, exporter

	def test_outsider_cannot_export_the_recipe_at_all(self):
		"""FM Production Manager has no export right, so the path is closed."""
		frappe.set_user(self.outsider)
		with self.assertRaises(frappe.PermissionError):
			self.exported_fieldnames()

	def test_exporter_strips_the_formula_for_a_permitted_exporter(self):
		"""The field-level guarantee, for a user who *may* export.

		Read and export are granted at permlevel 0 only, and the export request
		explicitly asks for the formula. It must still not come out.
		"""
		role = fixtures.ensure_level0_role("FM Recipe", "Exporter", read=1, export=1, report=1)
		exporter_user = fixtures.ensure_user("exporter", (role,))
		frappe.set_user(exporter_user)

		exported, exporter = self.exported_fieldnames()

		for fieldname in CONFIDENTIAL_PARENT_FIELDS + CONFIDENTIAL_CHILD_FIELDS:
			self.assertNotIn(fieldname, exported, msg=f"{fieldname} is exportable")

		# The header fields they are allowed to see still come through.
		self.assertIn("item", exported)

		# And no percentage value appears anywhere in the exported rows.
		flat = [str(cell) for row in exporter.csv_array for cell in row]
		self.assertNotIn("60.0", flat)
		self.assertNotIn("60", flat)

	def test_export_template_includes_the_formula_for_the_recipe_manager(self):
		frappe.set_user(self.insider)
		exported, _exporter = self.exported_fieldnames()
		self.assertIn("percentage", exported)
		self.assertIn("total_percentage", exported)

	# -- writing is restricted too -------------------------------------------

	def test_outsider_cannot_write_the_recipe_at_all(self):
		"""FM Production Manager is read-only, so the save is refused outright."""
		frappe.set_user(self.outsider)
		doc = frappe.get_doc("FM Recipe", self.recipe.name)
		doc.batch_size = 200
		with self.assertRaises(frappe.PermissionError):
			doc.save()

	def test_level_zero_writer_cannot_change_the_formula(self):
		"""The real permlevel guarantee.

		A user who *may* edit the recipe header but has no permlevel-1 access
		must not be able to change a percentage. Frappe discards such values in
		``reset_values_if_no_permlevel_access`` rather than raising, so this
		asserts the stored value is unchanged.
		"""
		from frappe.permissions import add_permission, update_permission_property

		role = "_FMT Level0 Writer"
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)  # test bootstrap

		add_permission("FM Recipe", role, 0)
		update_permission_property("FM Recipe", role, 0, "write", 1)
		frappe.clear_cache()

		writer = fixtures.ensure_user("level0", (role,))
		frappe.set_user(writer)

		doc = frappe.get_doc("FM Recipe", self.recipe.name)
		doc.batch_size = 150
		doc.ingredients[0].percentage = 99
		doc.ingredients[1].percentage = 1
		doc.save()

		frappe.set_user("Administrator")
		doc.reload()
		# The header edit is applied...
		self.assertEqual(doc.batch_size, 150)
		# ...but the formula is not.
		by_item = {row.item_code: row.percentage for row in doc.ingredients}
		self.assertEqual(by_item[self.chilli], 60)
		self.assertEqual(by_item[self.cumin], 40)

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

A fourth path is not the recipe at all: approving one generates a standard
submitted ``BOM`` whose rows carry the same quantities, and ERPNext gives
**Manufacturing User** read on BOM - a role every console operator needs. The
bulk routes to those rows are closed in ``overrides/bom.py`` and tested here,
and what deliberately stays open is documented in ``recipe_access``.
"""

import frappe
from frappe.utils import flt

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

	# -- path 4: the production console ---------------------------------------

	def work_order_for_the_recipe(self, qty=100):
		"""A submitted run against the BOM this recipe generates."""
		self.recipe.submit()

		doc = frappe.get_doc(
			{
				"doctype": "Work Order",
				"production_item": self.blend,
				"bom_no": self.recipe.bom,
				"qty": qty,
				"company": self.site["company"],
				"fg_warehouse": self.site["stores"],
				"wip_warehouse": self.site["stores"],
				"source_warehouse": self.site["stores"],
				"use_multi_level_bom": 0,
				"skip_transfer": 1,
			}
		)
		doc.insert()
		doc.submit()
		return doc

	def console_user(self, suffix, fm_role):
		"""An operator account: an FM role plus the ERPNext roles it needs.

		Work Order and Batch are ERPNext's own documents; this app does not
		widen access to them through its roles, so the standard ones come too.
		"""
		return fixtures.ensure_user(suffix, (fm_role, "Manufacturing User", "Item Manager"))

	def test_the_console_withholds_ingredient_quantities_from_an_outsider(self):
		"""Quantities are percentages once the batch size is known.

		60 kg of chilli in a 100 kg run *is* the 60% the recipe keeps at
		permlevel 1, so the production console must not hand it to an account
		that cannot read the recipe - otherwise the permlevel only protects the
		recipe form.
		"""
		from food_manufacturing.api.production import get_work_order_detail

		work_order = self.work_order_for_the_recipe()
		frappe.set_user(self.console_user("console_out", "FM Production Manager"))

		detail = get_work_order_detail(work_order.name)

		self.assertFalse(detail["shows_ingredient_detail"])
		self.assertTrue(detail["ingredients"])
		for row in detail["ingredients"]:
			# Which ingredients, and whether they are there, an operator needs.
			self.assertTrue(row["item_code"])
			self.assertIn(row["short"], (True, False, None))
			# How much of each, they do not get.
			for fieldname in ("required_qty", "transferred_qty", "consumed_qty", "short_qty"):
				self.assertIsNone(row[fieldname], msg=f"{row['item_code']}.{fieldname}")

	def test_the_console_gives_the_quantities_to_a_recipe_manager(self):
		from food_manufacturing.api.production import get_work_order_detail

		work_order = self.work_order_for_the_recipe()
		frappe.set_user(self.console_user("console_in", "FM Recipe Manager"))

		detail = get_work_order_detail(work_order.name)

		self.assertTrue(detail["shows_ingredient_detail"])
		quantities = {row["item_code"]: row["required_qty"] for row in detail["ingredients"]}
		self.assertEqual(quantities[self.chilli], 60)
		self.assertEqual(quantities[self.cumin], 40)

	def test_readiness_survives_the_formula_check(self):
		"""Withholding the numbers must not make a run look ready.

		There is no stock for this run, so it is short of both ingredients. The
		screen has to keep saying so without quoting how much.
		"""
		from food_manufacturing.api.production import get_work_order_detail

		work_order = self.work_order_for_the_recipe()
		frappe.set_user(self.console_user("console_ready", "FM Production Manager"))

		detail = get_work_order_detail(work_order.name)

		self.assertFalse(detail["material_ready"])
		self.assertTrue(all(row["short"] for row in detail["ingredients"]))
		self.assertFalse(detail["next_action"]["enabled"])

	# -- path 4: the BOM the approval generated -------------------------------

	def bom_rows(self, bom):
		"""The lines, asked for the way a caller would ask for them directly.

		``/api/resource/BOM Item?parent=BOM`` lands here. v16 answers it by
		joining ``tabBOM`` and applying *BOM's* permission conditions, which is
		why the rule is registered on BOM and reaches the child rows too.
		"""
		return frappe.get_list(
			"BOM Item",
			parent_doctype="BOM",
			filters={"parent": bom},
			fields=["item_code", "qty"],
			order_by="idx asc",
		)

	def test_the_generated_boms_rows_are_hidden_from_an_outsider(self):
		"""The formula survives into the BOM; the bulk route to it is closed.

		A console operator holds Manufacturing User for the production screen,
		and Manufacturing User reads BOM - so without this they could ask for
		every recipe's quantities in one request.
		"""
		self.recipe.submit()
		frappe.set_user(self.console_user("bom_out", "FM Production Manager"))

		self.assertEqual(self.bom_rows(self.recipe.bom), [])

	def test_the_generated_boms_rows_are_visible_to_a_recipe_manager(self):
		self.recipe.submit()
		frappe.set_user(self.console_user("bom_in", "FM Recipe Manager"))

		rows = self.bom_rows(self.recipe.bom)

		self.assertEqual(
			{row.item_code: flt(row.qty) for row in rows},
			{self.chilli: 60, self.cumin: 40},
		)

	def test_a_bom_no_recipe_generated_is_not_gated(self):
		"""This app does not decide who reads other people's BOMs.

		The marker is cleared rather than a second BOM built, because the marker
		is the whole of the rule: with it gone the very same query must answer.
		"""
		self.recipe.submit()
		bom = self.recipe.bom
		frappe.db.set_value("BOM", bom, "fm_recipe", None, update_modified=False)
		frappe.clear_document_cache("BOM", bom)

		frappe.set_user(self.console_user("bom_plain", "FM Production Manager"))

		self.assertTrue(self.bom_rows(bom))

	def test_an_outsider_cannot_take_a_copy_of_the_generated_bom(self):
		"""Print and email are how a document leaves the system wholesale.

		ERPNext grants both to Manufacturing User, so both are refused for a
		BOM that carries a formula this account may not read.
		"""
		self.recipe.submit()
		frappe.set_user(self.console_user("bom_print", "FM Production Manager"))
		doc = frappe.get_doc("BOM", self.recipe.bom)

		for right in ("print", "email"):
			self.assertFalse(
				frappe.has_permission("BOM", right, doc=doc),
				msg=f"{right} on a recipe's BOM was allowed",
			)

	def test_reading_the_bom_is_deliberately_still_allowed(self):
		"""Costing is built on it: the totals are given, the lines are not.

		Denying document read would take the cost screen away from the people it
		was written for - see the module docstring of ``overrides/bom.py``.
		"""
		self.recipe.submit()
		frappe.set_user(self.console_user("bom_read", "FM Production Manager"))
		doc = frappe.get_doc("BOM", self.recipe.bom)

		self.assertTrue(frappe.has_permission("BOM", "read", doc=doc))

	def test_a_recipe_manager_can_still_print_the_bom(self):
		"""The rule turns on the formula, not on the BOM being generated."""
		self.recipe.submit()
		frappe.set_user(self.console_user("bom_print_in", "FM Recipe Manager"))
		doc = frappe.get_doc("BOM", self.recipe.bom)

		self.assertTrue(frappe.has_permission("BOM", "print", doc=doc))

	def test_the_generated_bom_is_hidden_from_a_list_query_too(self):
		"""The same rule, on the route a report view or Desk list would take."""
		self.recipe.submit()
		frappe.set_user(self.console_user("bom_list", "FM Production Manager"))

		names = frappe.get_list("BOM", filters={"name": self.recipe.bom}, pluck="name")

		self.assertEqual(names, [])

	def test_costing_can_still_list_and_cost_the_bom(self):
		"""Totals without lines is the deliberate exception to the rule above.

		``get_costable_boms`` reads with ``get_all`` and checks read on BOM and
		the company as a document, precisely so the screen that is meant to give
		an operator the totals is not emptied by the rule that hides the lines.
		"""
		from food_manufacturing.api.costing import get_costable_boms

		self.recipe.submit()
		# Stock User as well, because the endpoint now checks the company as a
		# document - which is what `access.js` already lists for this screen.
		frappe.set_user(
			fixtures.ensure_user(
				"bom_cost",
				("FM Production Manager", "Manufacturing User", "Item Manager", "Stock User"),
			)
		)

		names = [row["name"] for row in get_costable_boms(self.site["company"])]

		self.assertIn(self.recipe.bom, names)

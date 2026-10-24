"""Acceptance examples for the recipe cost simulator.

The worked example throughout: a 100 kg blend of 60% chilli at 100/kg and 40%
cumin at 50/kg costs 6,000 + 2,000 = **8,000** in material. At 100% yield that
is 80.00 per kg; at 97% yield the same 8,000 spreads over 97 kg, so 82.47 per
kg. A 50 g pack holds 0.05 kg, so it carries 4.12 of blend.
"""

import frappe
from frappe.utils import flt

from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.costing.simulator import simulate
from food_manufacturing.tests import fixtures

KG = "Kg"
CHILLI_RATE = 100.0
CUMIN_RATE = 50.0


class TestCostSimulator(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		fixtures.ensure_uom(KG)

	def setUp(self):
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		fixtures.cleanup_users()

		self.tag = self._testMethodName.replace("test_", "")[:16]
		# Costing does not care about lots, and batch-tracked receipts would
		# drag the site's Serial and Batch setting into a pricing test.
		self.chilli = fixtures.ensure_item(
			f"ACostChilli {self.tag}", nature="Raw Material", has_batch=False
		)
		self.cumin = fixtures.ensure_item(
			f"ACostCumin {self.tag}", nature="Raw Material", has_batch=False
		)
		self.blend = fixtures.ensure_item(
			f"ACostBlend {self.tag}", nature="Bulk Blend", has_batch=False
		)

		# Priced through stock, so the BOM's own "Valuation Rate" source has
		# something real to resolve - no price is invented for the test.
		self.receive(self.chilli, 200, CHILLI_RATE)
		self.receive(self.cumin, 200, CUMIN_RATE)

		self.recipe = self.approve_recipe()
		self.bom = self.recipe.bom

	def tearDown(self):
		frappe.set_user("Administrator")
		fixtures.cleanup_recipes()
		fixtures.cleanup()
		fixtures.cleanup_users()

	def receive(self, item_code, qty, rate):
		doc = frappe.get_doc({
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"purpose": "Material Receipt",
			"company": self.site["company"],
			"items": [{
				"item_code": item_code,
				"qty": qty,
				"t_warehouse": self.site["stores"],
				"basic_rate": rate,
			}],
		})
		doc.insert()
		doc.submit()
		return doc

	def approve_recipe(self):
		doc = frappe.get_doc({
			"doctype": "FM Recipe",
			"item": self.blend,
			"company": self.site["company"],
			"batch_size": 100,
			"batch_uom": KG,
			"ingredients": [
				{"item_code": self.chilli, "percentage": 60, "uom": KG},
				{"item_code": self.cumin, "percentage": 40, "uom": KG},
			],
		})
		doc.insert()
		doc.submit()
		return doc

	# --- the worked example -------------------------------------------------

	def test_material_cost_for_one_batch(self):
		baseline = simulate(self.bom)["baseline"]

		self.assertAlmostEqual(baseline["ingredient_cost"], 8000.0, places=2)
		self.assertAlmostEqual(baseline["total_cost"], 8000.0, places=2)
		self.assertAlmostEqual(baseline["cost_per_unit"], 80.0, places=2)

	def test_batch_size_scales_cost_but_not_unit_cost(self):
		half = simulate(self.bom, batch_qty=50)["baseline"]

		self.assertAlmostEqual(half["ingredient_cost"], 4000.0, places=2)
		self.assertAlmostEqual(half["cost_per_unit"], 80.0, places=2)

	def test_yield_makes_each_surviving_kilogram_dearer(self):
		result = simulate(self.bom, yield_percent=97)

		self.assertAlmostEqual(result["scenario"]["good_qty"], 97.0, places=2)
		# 8,000 over 97 kg, not over 100.
		self.assertAlmostEqual(result["scenario"]["cost_per_unit"], 8000.0 / 97.0, places=2)
		# The material cost itself does not move: the same inputs went in.
		self.assertAlmostEqual(result["delta"]["ingredient_cost"]["change"], 0.0, places=2)
		self.assertGreater(result["delta"]["cost_per_unit"]["change"], 0)

	def test_a_price_rise_is_compared_against_the_baseline(self):
		result = simulate(self.bom, overrides={self.chilli: {"rate": 120}})

		self.assertAlmostEqual(result["baseline"]["ingredient_cost"], 8000.0, places=2)
		# 60 kg now at 120 = 7,200, plus cumin 2,000.
		self.assertAlmostEqual(result["scenario"]["ingredient_cost"], 9200.0, places=2)
		self.assertAlmostEqual(result["delta"]["total_cost"]["change"], 1200.0, places=2)
		self.assertAlmostEqual(result["delta"]["total_cost"]["percent"], 15.0, places=2)

	def test_a_quantity_change_is_compared_against_the_baseline(self):
		result = simulate(self.bom, overrides={self.cumin: {"qty_per_batch": 50}})

		# Chilli 6,000 unchanged; cumin now 50 kg at 50 = 2,500.
		self.assertAlmostEqual(result["scenario"]["ingredient_cost"], 8500.0, places=2)
		self.assertAlmostEqual(result["delta"]["ingredient_cost"]["change"], 500.0, places=2)

	def test_cost_per_pack_follows_the_declared_fill_quantity(self):
		pack = fixtures.ensure_item(
			f"ACostPack {self.tag}", nature="Finished Good", has_batch=False
		)
		frappe.db.set_value("Item", pack, {
			"fm_bulk_item": self.blend,
			"fm_pack_size": 0.05,
			"fm_pack_uom": KG,
		})
		frappe.clear_document_cache("Item", pack)

		baseline = simulate(self.bom, packs=[{"item_code": pack}])["baseline"]
		row = baseline["packs"][0]

		self.assertAlmostEqual(row["packs_per_batch"], 2000.0, places=2)
		self.assertAlmostEqual(row["cost_per_pack"], 4.0, places=4)

	def test_a_pack_without_a_fill_quantity_says_so(self):
		pack = fixtures.ensure_item(
			f"ACostNoFill {self.tag}", nature="Finished Good", has_batch=False
		)

		baseline = simulate(self.bom, packs=[{"item_code": pack}])["baseline"]
		row = baseline["packs"][0]

		# Never a number built on a guess.
		self.assertIsNone(row["cost_per_pack"])
		self.assertIn("pack size", row["note"].lower())

	# --- what a simulation must never do ------------------------------------

	def test_simulating_does_not_touch_the_bom(self):
		before = frappe.get_doc("BOM", self.bom)
		snapshot = (before.modified, flt(before.raw_material_cost), flt(before.total_cost))

		simulate(self.bom, batch_qty=250, yield_percent=80,
		         overrides={self.chilli: {"rate": 999}}, operating_cost=5000)

		after = frappe.get_doc("BOM", self.bom)
		self.assertEqual((after.modified, flt(after.raw_material_cost), flt(after.total_cost)), snapshot)

	def test_simulating_posts_no_stock(self):
		before = frappe.db.count("Stock Ledger Entry", {"company": self.site["company"]})
		simulate(self.bom, batch_qty=500, overrides={self.cumin: {"rate": 1}})
		self.assertEqual(
			frappe.db.count("Stock Ledger Entry", {"company": self.site["company"]}), before
		)

	def test_an_estimate_is_labelled_as_one(self):
		result = simulate(self.bom)

		self.assertEqual(result["basis"], "estimate")
		self.assertTrue(
			any("not ledger valuation" in note for note in result["baseline"]["assumptions"])
		)

	def test_assumptions_name_the_price_source(self):
		notes = " ".join(simulate(self.bom)["baseline"]["assumptions"])
		self.assertIn("Valuation Rate", notes)

	def test_each_line_carries_its_price_source_and_conversion(self):
		rows = simulate(self.bom)["baseline"]["ingredients"]
		self.assertTrue(rows)
		for row in rows:
			self.assertTrue(row["rate_source"])
			self.assertEqual(flt(row["conversion_factor"]), 1.0)
			self.assertEqual(row["uom"], KG)

	def test_json_string_arguments_are_accepted(self):
		"""Over HTTP every argument arrives as a string, not a dict."""
		result = simulate(
			self.bom,
			batch_qty="50",
			overrides=frappe.as_json({self.chilli: {"rate": 120}}),
			packs=frappe.as_json([]),
		)

		self.assertAlmostEqual(result["baseline"]["ingredient_cost"], 4000.0, places=2)
		# 30 kg of chilli at 120 = 3,600, plus 20 kg of cumin at 50 = 1,000.
		self.assertAlmostEqual(result["scenario"]["ingredient_cost"], 4600.0, places=2)

	def test_the_pack_picker_lists_only_this_blends_packs(self):
		"""Nothing is inferred about which SKUs a blend fills; the Item says."""
		from food_manufacturing.api.costing import get_packs_for

		mine = fixtures.ensure_item(f"ACostPackA {self.tag}", nature="Finished Good", has_batch=False)
		other = fixtures.ensure_item(f"ACostPackB {self.tag}", nature="Finished Good", has_batch=False)
		frappe.db.set_value("Item", mine, {"fm_bulk_item": self.blend, "fm_pack_size": 0.05})
		frappe.db.set_value("Item", other, {"fm_pack_size": 0.1})
		frappe.clear_document_cache("Item", mine)
		frappe.clear_document_cache("Item", other)

		codes = {row["item_code"] for row in get_packs_for(self.blend)}
		self.assertIn(mine, codes)
		self.assertNotIn(other, codes)

	def test_a_packaging_bom_offers_its_own_pack(self):
		"""Nothing is filled *from* a pack, so the picker would be empty."""
		from food_manufacturing.api.costing import get_packs_for

		pack = fixtures.ensure_item(f"ACostSelf {self.tag}", nature="Finished Good", has_batch=False)
		frappe.db.set_value("Item", pack, "fm_pack_size", 0.05)
		frappe.clear_document_cache("Item", pack)

		codes = {row["item_code"] for row in get_packs_for(pack)}
		self.assertEqual(codes, {pack})

	# --- permission and state -----------------------------------------------

	def test_a_deactivated_bom_cannot_be_costed(self):
		"""Costing a retired BOM would quote a formula nobody makes any more."""
		doc = frappe.get_doc("BOM", self.bom)
		doc.db_set("is_active", 0)
		frappe.clear_document_cache("BOM", self.bom)

		try:
			with self.assertRaises(frappe.ValidationError):
				simulate(self.bom)
		finally:
			# Restored here, not in tearDown: a deactivated BOM left behind
			# makes whichever test next picks it fail, and that failure looks
			# like a regression somewhere else entirely.
			doc.db_set("is_active", 1)
			frappe.clear_document_cache("BOM", self.bom)


	def test_a_user_without_bom_access_is_refused(self):
		user = fixtures.ensure_user("costnobody", ())
		frappe.set_user(user)

		with self.assertRaises(frappe.PermissionError):
			simulate(self.bom)

	def test_totals_are_given_without_the_formula_to_a_non_recipe_manager(self):
		"""Costing must not become the way around recipe confidentiality."""
		user = fixtures.ensure_user("costmgr", ("FM Production Manager", "Manufacturing User", "Item Manager"))
		frappe.set_user(user)

		result = simulate(self.bom)

		self.assertFalse(result["shows_ingredient_detail"])
		self.assertEqual(result["baseline"]["ingredients"], [])
		# The number they are entitled to is still there.
		self.assertAlmostEqual(result["baseline"]["ingredient_cost"], 8000.0, places=2)

	def test_the_recipe_manager_sees_the_lines(self):
		user = fixtures.ensure_user(
			"costrecipe", ("FM Recipe Manager", "Manufacturing User", "Item Manager")
		)
		frappe.set_user(user)

		result = simulate(self.bom)

		self.assertTrue(result["shows_ingredient_detail"])
		self.assertEqual(len(result["baseline"]["ingredients"]), 2)

	def test_an_override_is_refused_to_a_non_recipe_manager(self):
		"""Withholding the lines is not enough on its own.

		An override turns the totals into a measuring instrument: raise one
		ingredient's rate by 1 and the change in total cost *is* that
		ingredient's quantity. Repeat per item and the formula falls out of a
		read-only endpoint - so the override is refused rather than answered.
		"""
		user = fixtures.ensure_user(
			"costprobe", ("FM Production Manager", "Manufacturing User", "Item Manager")
		)
		frappe.set_user(user)

		with self.assertRaises(frappe.PermissionError):
			simulate(self.bom, overrides={self.chilli: {"rate": CHILLI_RATE + 1}})

	def test_yield_and_operating_cost_may_still_be_varied_without_the_formula(self):
		"""Neither varies by ingredient, so neither can single one out."""
		user = fixtures.ensure_user(
			"costyield", ("FM Production Manager", "Manufacturing User", "Item Manager")
		)
		frappe.set_user(user)

		result = simulate(self.bom, yield_percent=90, operating_cost=500)

		self.assertFalse(result["shows_ingredient_detail"])
		self.assertAlmostEqual(result["scenario"]["total_cost"], 8500.0, places=2)
		self.assertEqual(result["scenario"]["ingredients"], [])

	def test_a_pack_written_in_grams_is_converted_to_the_batch_unit(self):
		"""The fill is 50 g; the batch is costed in kilograms.

		Dividing one by the other without the factor is a 1,000x error in both
		directions at once - 2 packs at 4,000 each instead of 2,000 at 4.
		"""
		gram = fixtures.ensure_uom("Gram")
		fixtures.ensure_uom_conversion(KG, gram, 1000)

		pack = fixtures.ensure_item(
			f"ACostGramPack {self.tag}", nature="Finished Good", has_batch=False
		)
		frappe.db.set_value("Item", pack, {
			"fm_bulk_item": self.blend,
			"fm_pack_size": 50,
			"fm_pack_uom": gram,
		})
		frappe.clear_document_cache("Item", pack)

		row = simulate(self.bom, packs=[{"item_code": pack}])["baseline"]["packs"][0]

		self.assertAlmostEqual(row["packs_per_batch"], 2000.0, places=2)
		self.assertAlmostEqual(row["cost_per_pack"], 4.0, places=4)
		# The declared fill is reported as declared, with the factor beside it.
		self.assertEqual(row["pack_size"], 50)
		self.assertEqual(row["pack_uom"], gram)
		self.assertAlmostEqual(row["qty_per_pack"], 0.05, places=6)
		self.assertAlmostEqual(row["conversion"]["factor"], 0.001, places=6)
		self.assertEqual(row["conversion"]["to_uom"], KG)

	def test_a_pack_whose_unit_cannot_be_converted_says_so(self):
		"""Never a number built on a guess - the module's standing rule."""
		unknown = fixtures.ensure_uom("_FMT Jar")
		pack = fixtures.ensure_item(
			f"ACostJarPack {self.tag}", nature="Finished Good", has_batch=False
		)
		frappe.db.set_value("Item", pack, {
			"fm_bulk_item": self.blend,
			"fm_pack_size": 2,
			"fm_pack_uom": unknown,
		})
		frappe.clear_document_cache("Item", pack)

		row = simulate(self.bom, packs=[{"item_code": pack}])["baseline"]["packs"][0]

		self.assertIsNone(row["cost_per_pack"])
		self.assertIsNone(row["packs_per_batch"])
		self.assertIn("conversion", row["note"].lower())

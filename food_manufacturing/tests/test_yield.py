"""Planned versus actual yield, process loss and by-products.

``compute_yield`` is pure, so most of this exercises it directly against
realistic Work Order shapes. The UOM-honesty cases matter as much as the happy
path: a yield figure derived by adding kilograms to grams would be worse than no
figure at all.
"""

import frappe
from frappe.utils import flt

from food_manufacturing.compat.bom import byproduct_field, supports_work_order_byproducts
from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.production.yield_tracking import compute_yield
from food_manufacturing.tests import fixtures


class TestYield(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()

	def setUp(self):
		fixtures.cleanup()
		self.policy = fixtures.ensure_policy(self.site, yield_variance_tolerance_percent=2)

	def tearDown(self):
		fixtures.cleanup()

	def wo(self, **kwargs):
		kwargs.setdefault("company", self.site["company"])
		return build_work_order(**kwargs)

	# -- the acceptance scenario's blending step -----------------------------

	def test_blend_of_100kg_yielding_97kg(self):
		"""100 kg in, 97 kg usable blend out, 3 kg process loss."""
		doc = self.wo(
			required=[
				{"item_code": "A", "required_qty": 60, "consumed_qty": 60, "stock_uom": "Kg"},
				{"item_code": "B", "required_qty": 40, "consumed_qty": 40, "stock_uom": "Kg"},
			],
			qty=100,
			produced_qty=97,
			process_loss_qty=3,
		)
		figures = compute_yield(doc)

		self.assertEqual(flt(figures["fm_planned_input_qty"]), 100)
		self.assertEqual(flt(figures["fm_actual_input_qty"]), 100)
		self.assertEqual(flt(figures["fm_planned_yield_percent"]), 100)
		self.assertEqual(flt(figures["fm_actual_yield_percent"]), 97)
		self.assertEqual(flt(figures["fm_yield_variance_percent"]), -3)
		self.assertEqual(flt(figures["fm_process_loss_qty_snapshot"]), 3)
		self.assertEqual(figures["fm_yield_basis"], "Kg")

	def test_variance_beyond_tolerance_is_flagged(self):
		doc = self.wo(
			required=[{"item_code": "A", "required_qty": 100, "consumed_qty": 100, "stock_uom": "Kg"}],
			qty=100,
			produced_qty=97,
			process_loss_qty=3,
		)
		# 3% deviation against a 2% tolerance
		self.assertEqual(compute_yield(doc)["fm_yield_flagged"], 1)

	def test_variance_within_tolerance_is_not_flagged(self):
		doc = self.wo(
			required=[{"item_code": "A", "required_qty": 100, "consumed_qty": 100, "stock_uom": "Kg"}],
			qty=100,
			produced_qty=99,
			process_loss_qty=1,
		)
		self.assertEqual(compute_yield(doc)["fm_yield_flagged"], 0)

	def test_tolerance_comes_from_the_policy(self):
		fixtures.ensure_policy(self.site, yield_variance_tolerance_percent=5)
		doc = self.wo(
			required=[{"item_code": "A", "required_qty": 100, "consumed_qty": 100, "stock_uom": "Kg"}],
			qty=100,
			produced_qty=97,
			process_loss_qty=3,
		)
		self.assertEqual(compute_yield(doc)["fm_yield_flagged"], 0)

	def test_no_flag_without_a_policy(self):
		frappe.db.delete("FM Manufacturing Policy", {"company": self.site["company"]})
		doc = self.wo(
			required=[{"item_code": "A", "required_qty": 100, "consumed_qty": 100, "stock_uom": "Kg"}],
			qty=100,
			produced_qty=50,
		)
		self.assertEqual(compute_yield(doc)["fm_yield_flagged"], 0)

	# -- 4.4 loss and by-products are separate -------------------------------

	def test_byproducts_are_reported_separately_from_process_loss(self):
		"""Recoverable by-product and non-recoverable loss stay distinct figures.

		Where the version's Work Order carries no by-product table the
		by-product figure is necessarily zero, and process loss must still
		stand on its own - that is the contract either way.
		"""
		secondary = [{"item_code": "Oversize", "qty": 2}] if supports_work_order_byproducts() else None
		doc = self.wo(
			required=[{"item_code": "A", "required_qty": 100, "consumed_qty": 100, "stock_uom": "Kg"}],
			qty=100,
			produced_qty=95,
			process_loss_qty=3,
			secondary=secondary,
		)
		figures = compute_yield(doc)
		self.assertEqual(flt(figures["fm_process_loss_qty_snapshot"]), 3)
		self.assertEqual(flt(figures["fm_byproduct_qty"]), 2 if secondary else 0)

	def test_byproducts_read_through_the_compat_layer(self):
		"""The by-product table is reached only via compat/bom.py."""
		from food_manufacturing.compat.bom import get_byproducts

		required = [{"item_code": "A", "required_qty": 100, "consumed_qty": 100, "stock_uom": "Kg"}]

		if not supports_work_order_byproducts():
			# v15's Work Order has no by-product table at all, so the compat
			# layer reports none and callers can still iterate unconditionally.
			self.assertIsNone(byproduct_field("Work Order"))
			self.assertEqual(get_byproducts(self.wo(required=required)), [])
			return

		doc = self.wo(required=required, secondary=[{"item_code": "Oversize", "qty": 7}])
		self.assertEqual(byproduct_field("Work Order"), "secondary_items")
		self.assertEqual([flt(r.qty) for r in get_byproducts(doc)], [7])

	# -- UOM honesty ----------------------------------------------------------

	def test_mixed_uoms_do_not_produce_a_yield_figure(self):
		doc = self.wo(
			required=[
				{"item_code": "A", "required_qty": 60, "consumed_qty": 60, "stock_uom": "Kg"},
				{"item_code": "B", "required_qty": 40000, "consumed_qty": 40000, "stock_uom": "Gram"},
			],
			qty=100,
			produced_qty=97,
		)
		figures = compute_yield(doc)
		self.assertEqual(flt(figures["fm_actual_input_qty"]), 0)
		self.assertEqual(flt(figures["fm_actual_yield_percent"]), 0)
		self.assertEqual(figures["fm_yield_flagged"], 0)
		self.assertIn("mixed UOMs", figures["fm_yield_basis"])

	def test_ingredient_uom_differing_from_output_uom_is_refused(self):
		"""All in grams but the blend is in kg: still not comparable.

		The output UOM is read from the production Item, because ERPNext
		defaults Work Order.stock_uom to Nos.
		"""
		blend = fixtures.ensure_item("Yield Blend Kg", nature="Bulk Blend")
		doc = self.wo(
			required=[{"item_code": "A", "required_qty": 100000, "consumed_qty": 100000, "stock_uom": "Gram"}],
			qty=100,
			produced_qty=97,
			production_item=blend,
		)
		basis = compute_yield(doc)["fm_yield_basis"]
		self.assertIn("Gram", basis)
		self.assertIn("output in Kg", basis)

	# -- partial completion and empty states ---------------------------------

	def test_nothing_produced_yet(self):
		doc = self.wo(
			required=[{"item_code": "A", "required_qty": 100, "consumed_qty": 0, "stock_uom": "Kg"}],
			qty=100,
			produced_qty=0,
		)
		figures = compute_yield(doc)
		self.assertEqual(flt(figures["fm_planned_yield_percent"]), 100)
		# No input consumed yet, so there is no actual yield to report.
		self.assertEqual(flt(figures["fm_actual_yield_percent"]), 0)
		self.assertEqual(figures["fm_yield_flagged"], 0)

	def test_partial_completion(self):
		"""Half the batch made from half the input still yields 97%."""
		doc = self.wo(
			required=[{"item_code": "A", "required_qty": 100, "consumed_qty": 50, "stock_uom": "Kg"}],
			qty=100,
			produced_qty=48.5,
		)
		figures = compute_yield(doc)
		self.assertEqual(flt(figures["fm_actual_yield_percent"]), 97)

	def test_no_required_items(self):
		figures = compute_yield(self.wo(required=[]))
		self.assertEqual(figures["fm_yield_basis"], "No required items")
		self.assertEqual(figures["fm_yield_flagged"], 0)


def build_work_order(required, qty=100, produced_qty=0, process_loss_qty=0, stock_uom="Kg",
                     company=None, secondary=None, production_item=None):
	"""A real (unsaved) Work Order document, so .get() behaves normally."""
	doc = frappe.new_doc("Work Order")
	doc.company = company
	doc.qty = qty
	doc.produced_qty = produced_qty
	doc.process_loss_qty = process_loss_qty
	doc.stock_uom = stock_uom
	doc.production_item = production_item

	for row in required:
		doc.append("required_items", row)

	# Only v16+ carries a by-product table on the Work Order itself; on a
	# version without one there is nowhere to put these rows.
	fieldname = byproduct_field("Work Order")
	for row in secondary or []:
		doc.append(fieldname, row)

	return doc

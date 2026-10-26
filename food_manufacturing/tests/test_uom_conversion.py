"""UOM conversion: the same answers, and a bounded number of queries.

:func:`get_conversions` exists because the single-pair functions were being
called a row at a time from inside a whitelisted endpoint, and each call read
the Item plus up to two factor tables. The two things worth asserting are that
batching did not change any answer, and that it is actually a batch.
"""

from unittest.mock import patch

import frappe
from frappe.utils import flt

from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.packaging.conversion import (
	convert_qty,
	get_conversions,
	to_stock_qty,
)
from food_manufacturing.tests import fixtures

KG = "Kg"
GRAM = "Gram"


class TestUomConversion(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		fixtures.ensure_uom(KG)
		fixtures.ensure_uom(GRAM)
		fixtures.ensure_uom_conversion(KG, GRAM, 1000)

	def setUp(self):
		fixtures.cleanup()
		self.tag = self._testMethodName.replace("test_", "")[:16]
		self.blend = fixtures.ensure_item(
			f"AUomBlend {self.tag}", nature="Bulk Blend", has_batch=False
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		fixtures.cleanup()

	def test_grams_convert_into_the_batch_unit(self):
		"""A 50 g fill is 0.05 kg. Getting this wrong is a 1,000x error."""
		qty, factor, problem = convert_qty(self.blend, 50, GRAM, KG)

		self.assertIsNone(problem)
		self.assertEqual(flt(factor, 6), 0.001)
		self.assertEqual(flt(qty, 6), 0.05)

	def test_an_unknown_pair_is_reported_rather_than_assumed(self):
		"""ERPNext's own helper returns 1.0 when it finds nothing; this must not."""
		fixtures.ensure_uom("AUomNowhere")

		qty, factor, problem = convert_qty(self.blend, 50, "AUomNowhere", KG)

		self.assertTrue(problem)
		self.assertEqual(qty, 0.0)
		self.assertEqual(factor, 0.0)

	def test_the_same_unit_needs_no_conversion(self):
		self.assertEqual(convert_qty(self.blend, 50, KG, KG), (50.0, 1.0, None))

	def test_an_item_that_does_not_exist_is_reported(self):
		_qty, _factor, problem = to_stock_qty("AUomNoSuchItem", 1, GRAM)

		self.assertTrue(problem)

	def test_the_batch_answers_exactly_as_the_single_pair_calls_do(self):
		"""Parity is the whole contract: one implementation, two front doors."""
		pairs = [
			(self.blend, GRAM, KG),
			(self.blend, KG, KG),
			(self.blend, "AUomAlsoNowhere", KG),
		]
		fixtures.ensure_uom("AUomAlsoNowhere")

		batch = get_conversions(pairs)

		for key in pairs:
			item, from_uom, to_uom = key
			expected = convert_qty(item, 1, from_uom, to_uom)
			factor, problem = batch[key]

			if problem:
				self.assertTrue(expected[2], msg=f"{key} disagreed about failing")
				continue

			self.assertIsNone(expected[2], msg=f"{key} disagreed about succeeding")
			self.assertEqual(flt(factor, 9), flt(expected[1], 9), msg=str(key))

	def test_the_query_count_does_not_grow_with_the_number_of_rows(self):
		"""The point of the function: no query per row.

		Counted as "same for two pairs as for twelve" rather than as an absolute
		number, because the first read of a DocType also loads its meta - which
		is cached, real, and nothing to do with what this guards.
		"""
		items = [
			fixtures.ensure_item(
				f"AUomPack{idx} {self.tag}", nature="Finished Good", has_batch=False
			)
			for idx in range(12)
		]

		def count(pairs):
			with patch.object(frappe.db, "sql", wraps=frappe.db.sql) as spy:
				get_conversions(pairs)
				return spy.call_count

		# Warm the meta of all three tables so it is not counted below.
		count([(items[0], GRAM, KG)])

		few = count([(item, GRAM, KG) for item in items[:2]])
		many = count([(item, GRAM, KG) for item in items])

		self.assertEqual(few, many)
		self.assertLessEqual(many, 3)

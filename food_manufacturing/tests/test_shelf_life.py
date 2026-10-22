"""Expiry and remaining-shelf-life rules, and deterministic FEFO ordering."""

import frappe
from frappe.utils import add_days, flt, today

from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.dispatch.fefo import _fefo_sort_key, get_fefo_batches
from food_manufacturing.dispatch.shelf_life import remaining_shelf_life_percent
from food_manufacturing.tests import fixtures


class TestRemainingShelfLife(FMTestCase):
	"""The percentage calculation, including the cases it must refuse."""

	def test_half_way_through_shelf_life(self):
		detail = {
			"manufacturing_date": add_days(today(), -100),
			"expiry_date": add_days(today(), 100),
		}
		self.assertEqual(flt(remaining_shelf_life_percent(detail), 2), 50.0)

	def test_fresh_batch(self):
		detail = {
			"manufacturing_date": today(),
			"expiry_date": add_days(today(), 365),
		}
		self.assertEqual(flt(remaining_shelf_life_percent(detail), 2), 100.0)

	def test_expired_batch_is_zero_not_negative(self):
		detail = {
			"manufacturing_date": add_days(today(), -400),
			"expiry_date": add_days(today(), -35),
		}
		self.assertEqual(remaining_shelf_life_percent(detail), 0.0)

	def test_falls_back_to_item_shelf_life(self):
		"""No manufacturing date, but the Item declares a shelf life."""
		detail = {
			"manufacturing_date": None,
			"expiry_date": add_days(today(), 90),
			"shelf_life_in_days": 360,
		}
		self.assertEqual(flt(remaining_shelf_life_percent(detail), 2), 25.0)

	def test_unknown_total_shelf_life_returns_none(self):
		"""Refuse to guess: None, not a made-up percentage."""
		detail = {"manufacturing_date": None, "expiry_date": add_days(today(), 90)}
		self.assertIsNone(remaining_shelf_life_percent(detail))

	def test_no_expiry_date_returns_none(self):
		self.assertIsNone(remaining_shelf_life_percent({"expiry_date": None}))

	def test_zero_length_shelf_life_returns_none(self):
		"""Manufactured and expiring the same day: no sane denominator."""
		detail = {"manufacturing_date": today(), "expiry_date": today()}
		self.assertIsNone(remaining_shelf_life_percent(detail))


class TestFefoOrdering(FMTestCase):
	"""The ordering must be total, so the same inputs always give one answer."""

	def test_earlier_expiry_first(self):
		rows = [
			{"batch_no": "B", "expiry_date": "2027-01-01", "manufacturing_date": None},
			{"batch_no": "A", "expiry_date": "2026-01-01", "manufacturing_date": None},
		]
		self.assertEqual([r["batch_no"] for r in sorted(rows, key=_fefo_sort_key)], ["A", "B"])

	def test_never_expiring_batches_go_last(self):
		rows = [
			{"batch_no": "NOEXP", "expiry_date": None, "manufacturing_date": None},
			{"batch_no": "EXP", "expiry_date": "2030-01-01", "manufacturing_date": None},
		]
		self.assertEqual(
			[r["batch_no"] for r in sorted(rows, key=_fefo_sort_key)], ["EXP", "NOEXP"]
		)

	def test_manufacturing_date_breaks_an_expiry_tie(self):
		rows = [
			{"batch_no": "NEW", "expiry_date": "2027-01-01", "manufacturing_date": "2026-06-01"},
			{"batch_no": "OLD", "expiry_date": "2027-01-01", "manufacturing_date": "2026-01-01"},
		]
		self.assertEqual([r["batch_no"] for r in sorted(rows, key=_fefo_sort_key)], ["OLD", "NEW"])

	def test_batch_id_is_the_final_tie_break(self):
		"""Fully determined even when both dates are identical."""
		rows = [
			{"batch_no": "B-002", "expiry_date": "2027-01-01", "manufacturing_date": "2026-01-01"},
			{"batch_no": "B-001", "expiry_date": "2027-01-01", "manufacturing_date": "2026-01-01"},
		]
		self.assertEqual(
			[r["batch_no"] for r in sorted(rows, key=_fefo_sort_key)], ["B-001", "B-002"]
		)

	def test_ordering_is_stable_across_input_order(self):
		"""Shuffling the input must not change the output."""
		rows = [
			{"batch_no": f"B-{i:03d}", "expiry_date": "2027-01-01", "manufacturing_date": None}
			for i in range(8)
		]
		forward = [r["batch_no"] for r in sorted(rows, key=_fefo_sort_key)]
		backward = [r["batch_no"] for r in sorted(list(reversed(rows)), key=_fefo_sort_key)]
		self.assertEqual(forward, backward)


class TestFefoAgainstRealStock(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()
		fixtures.ensure_uom("Kg")

	def setUp(self):
		fixtures.cleanup()
		self.original_batch_setting = frappe.db.get_single_value(
			"Stock Settings", "enable_serial_and_batch_no_for_item"
		)
		frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

		self.policy = fixtures.ensure_policy(self.site)
		tag = self._testMethodName.replace("test_", "")[:16]
		self.item = fixtures.ensure_item(f"Fefo {tag}", nature="Finished Good")
		self.tag = tag

	def tearDown(self):
		fixtures.cleanup()
		frappe.db.set_single_value(
			"Stock Settings",
			"enable_serial_and_batch_no_for_item",
			self.original_batch_setting,
		)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

	def stock_batch(self, batch_id, qty, expiry, status="Released"):
		batch = fixtures.ensure_batch(self.item, batch_id, status=status)
		frappe.db.set_value("Batch", batch, "expiry_date", expiry)
		frappe.clear_document_cache("Batch", batch)

		doc = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"purpose": "Material Receipt",
				"company": self.site["company"],
				"items": [
					{
						"item_code": self.item,
						"qty": qty,
						"t_warehouse": self.site["stores"],
						"basic_rate": 100,
						"batch_no": batch,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		doc.insert()
		doc.submit()
		return batch

	def test_fefo_orders_real_stock_by_expiry(self):
		later = self.stock_batch(f"LATER-{self.tag}", 10, add_days(today(), 200))
		sooner = self.stock_batch(f"SOONER-{self.tag}", 10, add_days(today(), 20))

		order = [b["batch_no"] for b in get_fefo_batches(self.item, self.site["stores"])]
		self.assertEqual(order[:2], [sooner, later])

	def test_held_batches_are_not_recommended(self):
		self.stock_batch(f"HELD-{self.tag}", 10, add_days(today(), 20), status="Hold")
		released = self.stock_batch(f"OK-{self.tag}", 10, add_days(today(), 200))

		order = [b["batch_no"] for b in get_fefo_batches(self.item, self.site["stores"])]
		self.assertEqual(order, [released])

	def test_rejected_batches_are_not_recommended(self):
		self.stock_batch(f"REJ-{self.tag}", 10, add_days(today(), 20), status="Rejected")
		released = self.stock_batch(f"OK-{self.tag}", 10, add_days(today(), 200))

		order = [b["batch_no"] for b in get_fefo_batches(self.item, self.site["stores"])]
		self.assertEqual(order, [released])

	def test_recommendation_splits_across_batches(self):
		from food_manufacturing.dispatch.fefo import get_fefo_recommendation

		sooner = self.stock_batch(f"S-{self.tag}", 6, add_days(today(), 20))
		later = self.stock_batch(f"L-{self.tag}", 10, add_days(today(), 200))

		result = get_fefo_recommendation(self.item, self.site["stores"], 10, self.site["company"])
		picks = {p["batch_no"]: flt(p["suggested_qty"]) for p in result["batches"]}
		self.assertEqual(picks, {sooner: 6.0, later: 4.0})
		self.assertEqual(flt(result["shortfall"]), 0)

	def test_recommendation_reports_a_shortfall(self):
		from food_manufacturing.dispatch.fefo import get_fefo_recommendation

		self.stock_batch(f"ONLY-{self.tag}", 3, add_days(today(), 20))
		result = get_fefo_recommendation(self.item, self.site["stores"], 10, self.site["company"])
		self.assertEqual(flt(result["shortfall"]), 7)

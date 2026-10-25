"""Database-free regressions for QC, picking, recall quantities and retry decisions."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe

from food_manufacturing.api import dispatch, idempotency, quality, recall
from food_manufacturing.api.idempotency import retry_safe
from food_manufacturing.dispatch import fefo
from food_manufacturing.food_manufacturing_quality.doctype.fm_batch_release import fm_batch_release as release


class TestOperatorGuardsUnit(unittest.TestCase):
	def setUp(self):
		self.db = Mock()
		self.patches = [
			patch.object(frappe, "local", SimpleNamespace(flags=frappe._dict(in_test=False), request=None)),
			patch.object(idempotency, "_", side_effect=lambda value: value),
			patch.object(dispatch, "_", side_effect=lambda value: value),
			patch.object(fefo, "_", side_effect=lambda value: value),
			patch.object(frappe, "db", self.db),
			patch.object(frappe, "throw", side_effect=frappe.ValidationError("Blocked")),
			patch.object(release, "_", side_effect=lambda value: value),
			patch.object(frappe, "has_permission", return_value=True),
		]
		for context in self.patches:
			context.start()
			self.addCleanup(context.stop)

	def screening(self, inspection):
		doc = object.__new__(release.FMBatchRelease)
		doc.__dict__.update(decision="Release", company="Company", batch="LOT", quality_inspection="QI")
		self.db.get_value.side_effect = [frappe._dict(inspection), "SPICE"]
		return doc

	@patch.object(release, "get_policy", return_value=SimpleNamespace(require_incoming_inspection=1))
	def test_inspection_for_other_batch_cannot_release(self, policy):
		doc = self.screening(
			{"docstatus": 1, "status": "Accepted", "item_code": "SPICE", "batch_no": "OTHER"}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.validate_inspection_requirement()

	@patch.object(release, "get_policy", return_value=SimpleNamespace(require_incoming_inspection=1))
	def test_inspection_for_other_item_cannot_release(self, policy):
		doc = self.screening({"docstatus": 1, "status": "Accepted", "item_code": "OTHER", "batch_no": "LOT"})
		with self.assertRaises(frappe.ValidationError):
			doc.validate_inspection_requirement()

	@patch.object(release, "get_policy", return_value=SimpleNamespace(require_incoming_inspection=1))
	def test_accepted_matching_inspection_can_release(self, policy):
		doc = self.screening({"docstatus": 1, "status": "Accepted", "item_code": "SPICE", "batch_no": "LOT"})
		doc.validate_inspection_requirement()

	@patch.object(release, "get_policy", return_value=SimpleNamespace(require_incoming_inspection=1))
	def test_cancelled_inspection_cannot_release(self, policy):
		doc = self.screening({"docstatus": 1, "status": "Cancelled", "item_code": "SPICE", "batch_no": "LOT"})
		with self.assertRaises(frappe.ValidationError):
			doc.validate_inspection_requirement()

	def test_old_decision_cannot_overwrite_new_decision(self):
		doc = object.__new__(release.FMBatchRelease)
		doc.__dict__.update(name="OLD", batch="LOT", get_current_status=Mock(), update_batch=Mock())
		self.db.get_value.return_value = "NEW"
		with self.assertRaises(frappe.ValidationError):
			doc.revert_decision()
		doc.update_batch.assert_not_called()

	@patch.object(dispatch, "get_fefo_batches_bulk")
	@patch.object(dispatch, "get_batch_shelf_life", return_value={})
	@patch.object(dispatch, "get_policy_if_any", return_value=None)
	@patch.object(frappe, "get_doc")
	def test_cartons_allocate_in_stock_units(self, get_doc, policy, shelf, available):
		get_doc.return_value = SimpleNamespace(
			check_permission=Mock(),
			company="C",
			customer="BUYER",
			customer_name="Buyer",
			items=[
				SimpleNamespace(
					name="ROW",
					idx=1,
					item_code="SKU",
					item_name="Spice",
					qty=2,
					delivered_qty=0,
					conversion_factor=24,
					warehouse="W",
					uom="Carton",
					stock_uom="Nos",
					rate=100,
				)
			],
		)
		available.return_value = {("SKU", "W"): [{"batch_no": "B", "available_qty": 50}]}
		line = dispatch.get_picklist("SO")["lines"][0]
		self.assertEqual(line["suggestion"], [{"batch_no": "B", "qty": 48}])
		self.assertEqual(line["shortfall"], 0)
		self.assertEqual(line["candidates"][0]["available_qty"], 50)

	@patch.object(dispatch, "get_fefo_batches_bulk")
	@patch.object(dispatch, "get_batch_shelf_life")
	@patch.object(
		dispatch,
		"get_policy_if_any",
		return_value=SimpleNamespace(enforce_fefo="Block", min_remaining_shelf_life_percent=25),
	)
	@patch.object(frappe, "get_doc")
	def test_shelf_life_blocked_batch_is_not_suggested(self, get_doc, policy, shelf, available):
		get_doc.return_value = SimpleNamespace(
			check_permission=Mock(),
			company="C",
			customer="BUYER",
			customer_name="Buyer",
			items=[
				SimpleNamespace(
					name="ROW",
					idx=1,
					item_code="SKU",
					item_name="Spice",
					qty=2,
					delivered_qty=0,
					conversion_factor=1,
					warehouse="W",
					uom="Nos",
					stock_uom="Nos",
					rate=100,
				)
			],
		)
		available.return_value = {
			("SKU", "W"): [
				{"batch_no": "OLD", "available_qty": 50},
				{"batch_no": "FRESH", "available_qty": 10},
			]
		}
		shelf.return_value = {
			"OLD": {"expiry_date": "2026-11-01", "manufacturing_date": "2025-11-01"},
			"FRESH": {},
		}
		with patch.object(dispatch, "remaining_shelf_life_percent", side_effect=[10, None]):
			line = dispatch.get_picklist("SO")["lines"][0]
		self.assertEqual(line["suggestion"], [{"batch_no": "FRESH", "qty": 2}])

	@patch.object(quality, "get_item_uoms", return_value={"ITEM": "Kg"})
	@patch.object(quality, "get_batch_shelf_life", return_value={})
	@patch.object(quality, "get_batch_quantities", return_value={"LOCAL": 5})
	@patch.object(frappe, "get_all", return_value=["WAREHOUSE"])
	@patch.object(frappe, "get_list")
	def test_queue_pages_after_company_stock_filter(self, get_list, warehouses, quantities, shelf, uoms):
		get_list.return_value = [
			{"name": "FOREIGN", "item": "ITEM"},
			{"name": "LOCAL", "item": "ITEM"},
		]
		self.assertEqual([row["name"] for row in quality.get_release_queue("C", limit=1)], ["LOCAL"])

	@patch.object(quality, "get_item_uoms", return_value={"ITEM": "Kg"})
	@patch.object(quality, "get_batch_shelf_life", return_value={})
	@patch.object(quality, "get_batch_quantities", return_value={"LOCAL": 5})
	@patch.object(frappe, "get_all", return_value=["WAREHOUSE"])
	@patch.object(frappe, "get_list")
	def test_queue_rows_carry_their_unit(self, get_list, warehouses, quantities, shelf, uoms):
		"""450 of chilli could be kilograms or pouches; the queue must say."""
		get_list.return_value = [{"name": "LOCAL", "item": "ITEM"}]
		self.assertEqual(quality.get_release_queue("C")[0]["stock_uom"], "Kg")

	# The bundle rows come from compat.bundle.get_entries, which reads the
	# schema to decide where its columns live - so it is mocked as its own seam
	# rather than through frappe.get_all, keeping this test database-free.
	@patch.object(recall, "get_entries")
	@patch.object(frappe, "get_all")
	def test_recall_split_bundle_counts_only_affected_batch(self, get_all, get_entries):
		get_entries.return_value = [frappe._dict(parent="BUNDLE", batch_no="A", qty=-3)]
		get_all.return_value = [
			frappe._dict(
				voucher_no="DN",
				item_code="SKU",
				batch_no=None,
				actual_qty=-10,
				serial_and_batch_bundle="BUNDLE",
			)
		]
		rows = recall._movements({"A"}, "C", "Delivery Note")
		self.assertEqual(rows[0]["qty"], -3)

	def test_retry_returns_original_without_posting_again(self):
		@retry_safe("Sales Order", "sales_order", "Delivery Note", "delivery_note")
		def post(sales_order, lines, request_id=None):
			self.fail("A retry must not post again")

		import hashlib

		payload = hashlib.sha256(
			json.dumps({"sales_order": "SO", "lines": []}, sort_keys=True).encode()
		).hexdigest()
		self.db.get_value.side_effect = [
			"SO",
			frappe._dict(
				name="DN",
				docstatus=1,
				fm_operation_hash=payload,
				fm_operation_result='{"delivery_note":"DN"}',
			),
		]
		with patch.object(frappe, "session", SimpleNamespace(user="operator")):
			self.assertEqual(post("SO", [], request_id="retry"), {"delivery_note": "DN"})

	def test_retry_with_changed_payload_is_rejected(self):
		@retry_safe("Sales Order", "sales_order", "Delivery Note", "delivery_note")
		def post(sales_order, lines, request_id=None):
			self.fail("A mismatched retry must not post")

		self.db.get_value.side_effect = [
			"SO",
			frappe._dict(name="DN", docstatus=1, fm_operation_hash="other"),
		]
		with patch.object(frappe, "session", SimpleNamespace(user="operator")):
			with self.assertRaises(frappe.ValidationError):
				post("SO", [], request_id="retry")

	@patch.object(fefo, "get_fefo_batches_bulk")
	@patch.object(fefo, "get_batch_shelf_life", return_value={})
	def test_token_quantity_from_earliest_batch_does_not_bypass_fefo(self, shelf, available):
		available.return_value = {
			("SKU", "W"): [
				{"batch_no": "EARLY", "available_qty": 10},
				{"batch_no": "LATE", "available_qty": 10},
			]
		}
		rows = [
			frappe._dict(name="R1", item_code="SKU", warehouse="W", batch_no="EARLY", qty=1),
			frappe._dict(name="R2", item_code="SKU", warehouse="W", batch_no="LATE", qty=9),
		]
		self.assertTrue(fefo._find_breaches(rows, {"R1": {"EARLY"}, "R2": {"LATE"}}, "C"))

	@patch.object(fefo, "get_fefo_batches_bulk")
	@patch.object(fefo, "get_batch_shelf_life", return_value={})
	def test_valid_split_pick_exhausts_earliest_batch(self, shelf, available):
		available.return_value = {
			("SKU", "W"): [
				{"batch_no": "EARLY", "available_qty": 3},
				{"batch_no": "LATE", "available_qty": 10},
			]
		}
		rows = [
			frappe._dict(name="R1", item_code="SKU", warehouse="W", batch_no="EARLY", qty=3),
			frappe._dict(name="R2", item_code="SKU", warehouse="W", batch_no="LATE", qty=7),
		]
		self.assertEqual(fefo._find_breaches(rows, {"R1": {"EARLY"}, "R2": {"LATE"}}, "C"), [])

	@patch("food_manufacturing.stock_levels.get_reserved_batch_quantities", return_value={("B", "W"): 4})
	@patch("food_manufacturing.stock_levels.get_batch_balances", return_value={("B", "W"): 10})
	@patch.object(frappe, "get_all")
	def test_fefo_preserves_standard_batch_reservations(self, get_all, balances, reserved):
		get_all.return_value = [
			frappe._dict(
				name="B", item="SKU", expiry_date=None, manufacturing_date=None, fm_quality_status="Released"
			)
		]
		with patch.object(fefo, "getdate", return_value=__import__("datetime").date(2026, 10, 22)):
			rows = fefo.get_fefo_batches_bulk([("SKU", "W")])
		self.assertEqual(rows[("SKU", "W")][0]["available_qty"], 6)

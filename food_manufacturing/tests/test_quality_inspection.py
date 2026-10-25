"""Acceptance examples for raising and reading Quality Inspections.

The app already *checked* for an accepted inspection before release; it had no
way to raise one. These cover that, and the rule that matters most: every limit
comes from a template the plant configured, never from this app.
"""

import frappe

from food_manufacturing.compat.stock import get_lot_feature, set_lot_feature
from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.quality.inspection import (
	STAGES,
	create_inspection,
	get_inspections,
	get_readings,
)
from food_manufacturing.tests import fixtures

MOISTURE = "Moisture %"


class TestQualityInspection(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()

	def setUp(self):
		fixtures.cleanup_inspections()
		fixtures.cleanup()
		fixtures.cleanup_users()

		self.tag = self._testMethodName.replace("test_", "")[:14]
		self.policy = fixtures.ensure_policy(self.site)
		self.chilli = fixtures.ensure_item(f"AQIChilli {self.tag}", nature="Raw Material")
		self.template = self.ensure_template()
		frappe.db.set_value("Item", self.chilli, "quality_inspection_template", self.template)
		frappe.clear_document_cache("Item", self.chilli)

		self.batch = fixtures.ensure_batch(self.chilli, f"QI-{self.tag}", status="Quarantine")
		# The receipt the incoming check is an inspection *of*.
		self.receipt = self.receive(self.chilli, 50, self.batch).name

	def tearDown(self):
		frappe.set_user("Administrator")
		fixtures.cleanup_inspections()
		fixtures.cleanup()
		fixtures.cleanup_users()

	def ensure_template(self):
		"""The plant's own limits. Nothing here is supplied by the app."""
		name = f"{fixtures.PREFIX} Spice QC"
		# `specification` is a Link, so the parameter is a record in its own
		# right - which is the point: a plant curates its parameter list.
		if not frappe.db.exists("Quality Inspection Parameter", MOISTURE):
			frappe.get_doc({
				"doctype": "Quality Inspection Parameter",
				"parameter": MOISTURE,
			}).insert(ignore_permissions=True)  # test bootstrap

		if frappe.db.exists("Quality Inspection Template", name):
			return name

		frappe.get_doc({
			"doctype": "Quality Inspection Template",
			"quality_inspection_template_name": name,
			"item_quality_inspection_parameter": [
				{"specification": MOISTURE, "numeric": 1, "min_value": 0, "max_value": 12},
			],
		}).insert(ignore_permissions=True)  # test bootstrap
		return name

	def receive(self, item_code, qty, batch_no):
		original = get_lot_feature()
		set_lot_feature(1)
		try:
			doc = frappe.get_doc({
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"purpose": "Material Receipt",
				"company": self.site["company"],
				"items": [{
					"item_code": item_code, "qty": qty,
					"t_warehouse": self.site["quarantine"], "basic_rate": 100,
					"batch_no": batch_no, "use_serial_batch_fields": 1,
				}],
			})
			doc.insert()
			doc.submit()
			return doc
		finally:
			set_lot_feature(original)

	# --- the three stages ---------------------------------------------------

	def test_every_stage_maps_to_an_erpnext_inspection_type(self):
		self.assertEqual(STAGES["Incoming"], "Incoming")
		self.assertEqual(STAGES["In Process"], "In Process")
		# What the plant calls finished product, ERPNext calls outgoing.
		self.assertEqual(STAGES["Finished"], "Outgoing")

	def test_an_incoming_check_is_raised_against_the_batch(self):
		result = create_inspection(
			self.batch, "Incoming", "Stock Entry", self.receipt, 5)

		doc = frappe.get_doc("Quality Inspection", result["quality_inspection"])
		self.assertEqual(doc.inspection_type, "Incoming")
		self.assertEqual(doc.batch_no, self.batch)
		self.assertEqual(doc.item_code, self.chilli)
		self.assertEqual(doc.inspected_by, frappe.session.user)

	def test_in_process_and_finished_checks_are_raised_too(self):
		for stage, expected in (("In Process", "In Process"), ("Finished", "Outgoing")):
			result = create_inspection(self.batch, stage, "Stock Entry", self.receipt, 5)
			self.assertEqual(
				frappe.db.get_value("Quality Inspection", result["quality_inspection"], "inspection_type"),
				expected,
			)

	def test_an_unknown_stage_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			create_inspection(
			self.batch, "Midway", "Stock Entry", self.receipt, 5)

	# --- limits come from the template, never from this app -----------------

	def test_the_template_supplies_the_parameters_and_limits(self):
		result = create_inspection(
			self.batch, "Incoming", "Stock Entry", self.receipt, 5)

		self.assertEqual(result["template"], self.template)
		readings = get_readings(result["quality_inspection"])
		self.assertEqual([row["specification"] for row in readings], [MOISTURE])
		self.assertEqual(readings[0]["max_value"], 12)

	def test_an_item_without_a_template_cannot_be_inspected(self):
		"""Inventing a limit would be a food safety claim this app cannot make."""
		plain = fixtures.ensure_item(f"AQIPlain {self.tag}", nature="Raw Material")
		batch = fixtures.ensure_batch(plain, f"QIP-{self.tag}", status="Quarantine")

		with self.assertRaises(frappe.ValidationError) as caught:
			create_inspection(
			batch, "Incoming", "Stock Entry", self.receipt, 5)

		self.assertIn("Template", str(caught.exception))

	def test_a_reading_for_an_unknown_parameter_is_refused(self):
		"""Appending it would assert a limit nobody configured."""
		with self.assertRaises(frappe.ValidationError):
			create_inspection(
			self.batch, "Incoming", "Stock Entry", self.receipt, 5,
				readings=[{"specification": f"{fixtures.PREFIX} Lead ppm", "reading_value": "1"}],
			)

	def test_a_measured_value_is_recorded_against_its_parameter(self):
		result = create_inspection(
			self.batch, "Incoming", "Stock Entry", self.receipt, 5, readings=[{"specification": MOISTURE, "reading_value": "9"}]
		)

		readings = get_readings(result["quality_inspection"])
		self.assertEqual(readings[0]["reading_value"], "9")

	# --- evidence and history -----------------------------------------------

	def test_remarks_and_sample_size_are_recorded(self):
		result = create_inspection(
			self.batch, "Incoming", "Stock Entry", self.receipt, 5, remarks="Composite of 5 bags"
		)

		doc = frappe.get_doc("Quality Inspection", result["quality_inspection"])
		self.assertEqual(doc.remarks, "Composite of 5 bags")
		self.assertEqual(doc.sample_size, 5)

	def test_history_shows_a_rejected_inspection_too(self):
		"""Filtering to Accepted made the history a record of good news only."""
		create_inspection(
			self.batch, "Incoming", "Stock Entry", self.receipt, 5, status="Rejected", submit=True)

		rows = get_inspections(self.batch)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["status"], "Rejected")

	def test_history_is_newest_first_across_stages(self):
		create_inspection(
			self.batch, "Incoming", "Stock Entry", self.receipt, 5, submit=True)
		create_inspection(
			self.batch, "Finished", "Stock Entry", self.receipt, 5, submit=True)

		rows = get_inspections(self.batch)
		self.assertEqual(len(rows), 2)
		self.assertEqual(rows[0]["inspection_type"], "Outgoing")

	# --- permissions --------------------------------------------------------

	def test_a_user_without_create_permission_is_refused(self):
		user = fixtures.ensure_user("qinobody", ())
		frappe.set_user(user)

		with self.assertRaises(frappe.PermissionError):
			create_inspection(
			self.batch, "Incoming", "Stock Entry", self.receipt, 5)

	def test_an_inspector_may_raise_one(self):
		user = fixtures.ensure_user(
			"qiinspector", ("FM Quality Inspector", "Quality Manager", "Item Manager", "Stock User")
		)
		frappe.set_user(user)

		result = create_inspection(
			self.batch, "Incoming", "Stock Entry", self.receipt, 5)
		self.assertTrue(result["quality_inspection"])

	def test_a_reference_that_does_not_exist_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			create_inspection(self.batch, "Incoming", "Purchase Receipt", "PREC-nope", 5)

	def test_a_stage_cannot_be_filed_against_the_wrong_document(self):
		"""A finished-product check does not belong on a purchase receipt."""
		with self.assertRaises(frappe.ValidationError) as caught:
			create_inspection(self.batch, "Finished", "Purchase Receipt", self.receipt, 5)

		self.assertIn("cannot be filed against", str(caught.exception))

	def test_a_sample_size_of_zero_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			create_inspection(self.batch, "Incoming", "Stock Entry", self.receipt, 0)

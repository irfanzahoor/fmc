"""Server-side enforcement of FM Manufacturing Policy rules.

These tests deliberately do not create Companies. Creating a Company builds a
full chart of accounts and is effectively irreversible, which makes it unsafe
on a shared or populated site. Instead the fixtures *discover* two existing
companies that already have leaf warehouses, and skip when the site has none.
Only FM Manufacturing Policy rows - owned by this app - are written.
"""

import unittest

import frappe

from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.food_manufacturing_setup.doctype.fm_manufacturing_policy.fm_manufacturing_policy import (
	get_policy,
	get_policy_if_any,
)

#: A policy needs a quarantine and a rejected warehouse; the distinctness tests
#: need a third.
MIN_WAREHOUSES = 3


def find_fixtures():
	"""Return (company, [warehouses], foreign_company, foreign_warehouse).

	Returns None when the site cannot supply the shape the tests need.
	"""
	companies = frappe.get_all("Company", pluck="name", order_by="name")
	if len(companies) < 2:
		return None

	# One query for every candidate warehouse rather than one per company.
	rows = frappe.get_all(
		"Warehouse",
		filters={"company": ("in", companies), "is_group": 0},
		fields=["name", "company"],
		order_by="company asc, name asc",
	)

	by_company = {}
	for row in rows:
		by_company.setdefault(row.company, []).append(row.name)

	primary = next(
		(c for c in companies if len(by_company.get(c, [])) >= MIN_WAREHOUSES),
		None,
	)
	if not primary:
		return None

	foreign = next(
		(c for c in companies if c != primary and by_company.get(c)),
		None,
	)
	if not foreign:
		return None

	return primary, by_company[primary][:MIN_WAREHOUSES], foreign, by_company[foreign][0]


class TestFMManufacturingPolicy(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		fixtures = find_fixtures()
		if not fixtures:
			raise unittest.SkipTest(
				"Site needs two companies, one with at least "
				f"{MIN_WAREHOUSES} leaf warehouses"
			)

		cls.company, warehouses, cls.foreign_company, cls.foreign_warehouse = fixtures
		cls.quarantine, cls.rejected, cls.bulk = warehouses

	def setUp(self):
		# Policies are named after the company, so clear before each test.
		frappe.db.delete("FM Manufacturing Policy", {"company": self.company})

	def tearDown(self):
		frappe.db.delete("FM Manufacturing Policy", {"company": self.company})

	def make_policy(self, **overrides):
		values = {
			"doctype": "FM Manufacturing Policy",
			"company": self.company,
			"quarantine_warehouse": self.quarantine,
			"rejected_warehouse": self.rejected,
		}
		values.update(overrides)
		return frappe.get_doc(values)

	def test_policy_is_named_after_its_company(self):
		policy = self.make_policy()
		policy.insert()
		self.assertEqual(policy.name, self.company)

	def test_one_policy_per_company(self):
		self.make_policy().insert()
		with self.assertRaises(frappe.DuplicateEntryError):
			self.make_policy().insert()

	def test_warehouse_must_belong_to_company(self):
		policy = self.make_policy(bulk_warehouse=self.foreign_warehouse)
		with self.assertRaises(frappe.ValidationError):
			policy.insert()

	def test_quarantine_and_rejected_must_differ(self):
		policy = self.make_policy(rejected_warehouse=self.quarantine)
		with self.assertRaises(frappe.ValidationError):
			policy.insert()

	def test_bulk_cannot_reuse_rejected_warehouse(self):
		policy = self.make_policy(bulk_warehouse=self.rejected)
		with self.assertRaises(frappe.ValidationError):
			policy.insert()

	def test_percentage_above_hundred_is_rejected(self):
		policy = self.make_policy(min_remaining_shelf_life_percent=120)
		with self.assertRaises(frappe.ValidationError):
			policy.insert()

	def test_negative_percentage_is_rejected(self):
		policy = self.make_policy(yield_variance_tolerance_percent=-1)
		with self.assertRaises(frappe.ValidationError):
			policy.insert()

	def test_negative_alert_days_rejected(self):
		policy = self.make_policy(near_expiry_alert_days=-5)
		with self.assertRaises(frappe.ValidationError):
			policy.insert()

	def test_defaults_are_conservative(self):
		"""An unconfigured policy must default to blocking, not permitting."""
		policy = self.make_policy()
		policy.insert()
		self.assertEqual(policy.require_incoming_inspection, 1)
		self.assertEqual(policy.block_unreleased_consumption, 1)
		self.assertEqual(policy.block_rejected_consumption, 1)
		self.assertEqual(policy.block_expired_dispatch, 1)
		self.assertEqual(policy.enforce_fefo, "Warn")

	def test_get_policy_throws_when_missing(self):
		with self.assertRaises(frappe.ValidationError):
			get_policy(self.company)

	def test_get_policy_if_any_returns_none_when_missing(self):
		self.assertIsNone(get_policy_if_any(self.company))

	def test_get_policy_if_any_handles_blank_company(self):
		self.assertIsNone(get_policy_if_any(None))
		self.assertIsNone(get_policy_if_any(""))

	def test_disabled_policy_is_not_returned(self):
		self.make_policy(enabled=0).insert()
		self.assertIsNone(get_policy_if_any(self.company))

	def test_get_policy_returns_enabled_policy(self):
		self.make_policy().insert()
		self.assertEqual(get_policy(self.company).name, self.company)

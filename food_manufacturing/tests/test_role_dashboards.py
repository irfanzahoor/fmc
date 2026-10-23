"""Acceptance examples for the role-scoped dashboards and cost variance."""

import frappe

from food_manufacturing.api.dashboards import (
	DASHBOARDS,
	available_views,
	get_dashboard,
)
from food_manufacturing.compat.testing import FMTestCase
from food_manufacturing.costing.variance import summarise
from food_manufacturing.tests import fixtures


class TestRoleDashboards(FMTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.site = fixtures.require_site()

	def setUp(self):
		fixtures.cleanup()
		fixtures.cleanup_users()
		self.policy = fixtures.ensure_policy(self.site)

	def tearDown(self):
		frappe.set_user("Administrator")
		fixtures.cleanup()
		fixtures.cleanup_users()

	def metrics(self, panels):
		return {m["label"]: m for panel in panels for m in panel["metrics"]}

	# --- the four dashboards ------------------------------------------------

	def test_every_dashboard_builds(self):
		for view in DASHBOARDS:
			result = get_dashboard(self.site["company"], view)
			self.assertEqual(result["view"], view)
			self.assertTrue(result["panels"], f"{view} produced no panels")

	def test_an_unknown_dashboard_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			get_dashboard(self.site["company"], "accounts")

	def test_the_owner_sees_cost_variance(self):
		panels = get_dashboard(self.site["company"], "owner")["panels"]
		titles = [panel["title"] for panel in panels]

		self.assertIn("Cost variance", titles)
		self.assertIn("Variance", self.metrics(panels))

	def test_production_sees_the_work_queue(self):
		panels = get_dashboard(self.site["company"], "production")["panels"]
		self.assertIn("Work queue", [panel["title"] for panel in panels])

	def test_quality_sees_decisions_waiting(self):
		panels = get_dashboard(self.site["company"], "quality")["panels"]
		metrics = self.metrics(panels)

		self.assertIn("In quarantine", metrics)
		self.assertIn("On hold", metrics)

	def test_stores_sees_goods_in_and_near_expiry(self):
		titles = [p["title"] for p in get_dashboard(self.site["company"], "stores")["panels"]]

		self.assertIn("Goods in", titles)
		self.assertIn("Near expiry", titles)

	# --- every metric links to its source -----------------------------------

	def test_metrics_link_to_real_doctypes(self):
		"""A number nobody can open is a number nobody can check."""
		for view in DASHBOARDS:
			panels = get_dashboard(self.site["company"], view)["panels"]
			linked = [m for m in self.metrics(panels).values() if m["link"]]
			self.assertTrue(linked, f"{view} has no metric linking to source records")

			for metric in linked:
				self.assertTrue(
					frappe.db.exists("DocType", metric["link"]["doctype"]),
					f"{metric['label']} links to a DocType that does not exist",
				)
				self.assertIsInstance(metric["link"]["filters"], dict)

	def test_a_link_is_dropped_when_the_user_cannot_read_the_doctype(self):
		"""Better no link than one that refuses on click."""
		user = fixtures.ensure_user("dashops", ("FM Production Operator", "Manufacturing User", "Item Manager", "Stock User"))
		frappe.set_user(user)

		panels = get_dashboard(self.site["company"], "production")["panels"]
		for metric in self.metrics(panels).values():
			if metric["link"]:
				self.assertTrue(frappe.has_permission(metric["link"]["doctype"], "read"))

	# --- which dashboard a role lands on ------------------------------------

	def test_a_quality_manager_is_offered_the_quality_view(self):
		user = fixtures.ensure_user("dashqm", ("FM Quality Manager",))
		frappe.set_user(user)

		views = available_views()
		self.assertIn("quality", views)
		self.assertNotIn("stores", views)

	def test_a_storekeeper_is_offered_the_stores_view(self):
		user = fixtures.ensure_user("dashstore", ("FM Warehouse Operator",))
		frappe.set_user(user)

		self.assertEqual(available_views(), ["stores"])

	def test_a_user_with_no_fm_role_still_lands_somewhere(self):
		user = fixtures.ensure_user("dashnone", ("Stock User",))
		frappe.set_user(user)

		self.assertEqual(available_views(), ["production"])

	def test_a_system_manager_is_offered_every_view(self):
		self.assertEqual(available_views(), list(DASHBOARDS))

	# --- cost variance ------------------------------------------------------

	def test_an_unmeasurable_run_is_not_counted_as_on_plan(self):
		"""No BOM cost means no estimate - not an estimate of zero."""
		rows = [
			{"measured": False, "estimated_cost": None, "actual_cost": 500.0, "variance": None},
		]
		summary = summarise(rows)

		self.assertEqual(summary["runs"], 1)
		self.assertEqual(summary["measured_runs"], 0)
		self.assertIsNone(summary["variance"])

	def test_variance_is_actual_minus_estimated(self):
		rows = [
			{"measured": True, "estimated_cost": 8000.0, "actual_cost": 8400.0, "variance": 400.0},
			{"measured": True, "estimated_cost": 2000.0, "actual_cost": 1900.0, "variance": -100.0},
		]
		summary = summarise(rows)

		self.assertAlmostEqual(summary["estimated_cost"], 10000.0, places=2)
		self.assertAlmostEqual(summary["actual_cost"], 10300.0, places=2)
		self.assertAlmostEqual(summary["variance"], 300.0, places=2)
		self.assertAlmostEqual(summary["variance_percent"], 3.0, places=2)
		self.assertEqual(summary["over_plan_runs"], 1)

	def test_a_mixed_batch_says_how_many_runs_were_costed(self):
		panels = get_dashboard(self.site["company"], "owner")["panels"]
		cost = next(panel for panel in panels if panel["title"] == "Cost variance")

		# Either every run was costed (no note) or the note says how many were.
		if cost["note"]:
			self.assertIn("could be costed", cost["note"])

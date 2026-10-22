"""Two-process posting checks; commits only on the explicit disposable CI site.

Run after the normal suite: bench --site ci.localhost execute
food_manufacturing.tests.concurrency.run
"""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import frappe
from frappe import _

WORKER = """
import json, sys
import frappe
frappe.init(site=sys.argv[1], sites_path=sys.argv[2])
frappe.connect()
frappe.set_user("Administrator")
print("READY", flush=True)
sys.stdin.readline()
try:
	from food_manufacturing.api.production import finish_production_run
	result = finish_production_run(**json.loads(sys.argv[3]))
	frappe.db.commit()
	print(json.dumps({"ok": True, "result": result}))
except Exception as exc:
	frappe.db.rollback()
	print(json.dumps({"ok": False, "error": type(exc).__name__}))
finally:
	frappe.destroy()
"""


def run():
	if frappe.local.site != "ci.localhost" or not frappe.conf.get("fm_isolated_test_site"):
		frappe.throw(_("Concurrency checks require the disposable ci.localhost site."))
	from food_manufacturing.tests import fixtures
	from food_manufacturing.tests.test_api import APITestCase

	fixture = APITestCase(methodName="runTest")
	fixture.site = fixtures.require_site()
	fixture.setUp()
	try:
		fixture.receive(fixture.chilli, 120, "CONCURRENT-C")
		fixture.receive(fixture.cumin, 80, "CONCURRENT-U")
		recipe = fixture.approve_recipe()
		retry_order = fixture.make_work_order(recipe.bom)
		race_orders = [fixture.make_work_order(recipe.bom), fixture.make_work_order(recipe.bom)]
		# A deliberate test-harness commit: workers must observe the setup in their own connections.
		frappe.db.commit()
		request_id = str(uuid4())
		retried = _parallel([{"work_order": retry_order.name, "qty": 100, "request_id": request_id}] * 2)
		assert all(row["ok"] for row in retried), retried
		assert retried[0]["result"]["stock_entry"] == retried[1]["result"]["stock_entry"], retried
		raced = _parallel(
			[{"work_order": order.name, "qty": 100, "request_id": str(uuid4())} for order in race_orders]
		)
		assert sum(row["ok"] for row in raced) == 1, raced
		return {"same_request": "one stock posting", "competing_requests": "one winner"}
	finally:
		frappe.db.rollback()
		# Keep committed ledger fixtures intact for inspection; discard this CI site afterwards.
		frappe.db.set_single_value(
			"Stock Settings", "enable_serial_and_batch_no_for_item", fixture.original_batch_setting
		)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")
		frappe.db.commit()


def _parallel(payloads):
	site = frappe.local.site
	sites_path = str(Path(frappe.local.sites_path).resolve())
	barrier = Barrier(2)

	def execute(payload):
		process = subprocess.Popen(
			[sys.executable, "-c", WORKER, site, sites_path, json.dumps(payload)],
			stdin=subprocess.PIPE,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			text=True,
		)
		try:
			if process.stdout.readline().strip() != "READY":
				frappe.throw(_("A concurrency worker could not connect to the test site."))
			barrier.wait(timeout=90)
			stdout, stderr = process.communicate("\n", timeout=120)
			if process.returncode:
				frappe.throw(_("A concurrency worker failed: {0}").format(stderr))
			return json.loads(stdout.strip().splitlines()[-1])
		finally:
			if process.poll() is None:
				process.kill()
				process.wait()

	with ThreadPoolExecutor(max_workers=2) as pool:
		return list(pool.map(execute, payloads))

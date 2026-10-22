"""Demo data: the acceptance scenario, seeded as real ERPNext documents.

Everything is created through the normal document path, so the demo exercises
the same validations a real plant would hit - quarantine routing, the quality
gate, recipe approval, yield and loss, packaging genealogy, FEFO dispatch.

Three properties make this safe to run against a shared site:

* **Namespaced.** Every record this module creates is prefixed ``FM Demo``, so
  it is identifiable at a glance and removable in one call.
* **Idempotent.** Re-running skips what already exists rather than duplicating.
* **Reversible.** :func:`remove_demo_data` deletes what was created, newest
  document first, and restores the one site-wide setting the demo must change.

Run it::

    bench --site <site> execute food_manufacturing.demo.seed.create_demo_data
    bench --site <site> execute food_manufacturing.demo.seed.remove_demo_data
"""

import frappe
from frappe import _
from frappe.utils import add_days, flt, nowdate, today

PREFIX = "FM Demo"

#: Stock Settings must allow batch bundles or no batched stock can move at all.
BATCH_SETTING = "enable_serial_and_batch_no_for_item"
#: Remembered here so teardown only reverts a value this module changed.
BATCH_SETTING_FLAG = "fm_demo_restored_batch_setting"


def create_demo_data(company: str | None = None, verbose: bool = True) -> dict:
	"""Seed the full spice-manufacturing story. Safe to re-run."""
	company = _resolve_company(company)
	log = _logger(verbose)
	log(f"Seeding demo data for {company}")

	_enable_batch_setting(log)

	warehouses = _ensure_warehouses(company, log)
	_ensure_policy(company, warehouses, log)
	uoms = _ensure_uoms(log)
	parties = _ensure_parties(log)
	items = _ensure_items(company, log)

	lots = _receive_raw_materials(company, warehouses, items, log)
	_release_lots(company, lots, log)
	_move_decided_stock(company, warehouses, items, lots, log)

	recipe = _approve_recipe(company, items, uoms, log)
	blends = _run_blending(company, warehouses, items, recipe, log)
	packs = _run_packaging(company, warehouses, items, uoms, blends, log)
	_dispatch(company, warehouses, items, parties, packs, log)
	_add_ageing_stock(company, warehouses, items, lots, log)

	summary = _summarise(company, items, blends, packs)
	log("Done. " + ", ".join(f"{k}: {v}" for k, v in summary.items()))
	return summary


def remove_demo_data(company: str | None = None, verbose: bool = True) -> None:
	"""Delete everything :func:`create_demo_data` created."""
	log = _logger(verbose)
	log("Removing demo data")

	# A BOM and the FM Recipe that generated it point at each other, so neither
	# can be deleted while the other holds the link. Break it first.
	_unlink_recipes_and_boms(log)

	# Submitted documents must be cancelled before they can be deleted, and the
	# order matters: a later document references an earlier one.
	for doctype, filters in (
		("Delivery Note", {"customer": ("like", f"{PREFIX}%")}),
		("Stock Entry", {"remarks": ("like", f"{PREFIX}%")}),
		("FM Batch Release", {"batch": ("like", f"{PREFIX}%")}),
		("Work Order", {"production_item": ("like", f"{PREFIX}%")}),
		# BOM before FM Recipe: BOM.fm_recipe links back to the recipe, so the
		# recipe cannot be deleted while its BOM still exists.
		("BOM", {"item": ("like", f"{PREFIX}%")}),
		("FM Recipe", {"item": ("like", f"{PREFIX}%")}),
	):
		for name in frappe.get_all(doctype, filters=filters, pluck="name", order_by="creation desc"):
			_force_delete(doctype, name, log)

	for doctype, filters in (
		("Batch", {"name": ("like", f"{PREFIX}%")}),
		("Item", {"item_code": ("like", f"{PREFIX}%")}),
		("Supplier", {"supplier_name": ("like", f"{PREFIX}%")}),
		("Customer", {"customer_name": ("like", f"{PREFIX}%")}),
	):
		for name in frappe.get_all(doctype, filters=filters, pluck="name", order_by="creation desc"):
			_force_delete(doctype, name, log)

	_retire_warehouses(log)

	if frappe.db.get_default(BATCH_SETTING_FLAG):
		frappe.db.set_single_value("Stock Settings", BATCH_SETTING, 0)
		frappe.db.set_default(BATCH_SETTING_FLAG, None)
		log("Restored Stock Settings.enable_serial_and_batch_no_for_item to 0")

	log("Removed.")


def _unlink_recipes_and_boms(log) -> None:
	"""Clear the mutual link between a demo recipe and its generated BOM."""
	recipes = frappe.get_all(
		"FM Recipe", filters={"item": ("like", f"{PREFIX}%")}, pluck="name", order_by="name asc"
	)
	for name in recipes:
		frappe.db.set_value("FM Recipe", name, "bom", None, update_modified=False)

	boms = frappe.get_all(
		"BOM", filters={"item": ("like", f"{PREFIX}%")}, pluck="name", order_by="name asc"
	)
	for name in boms:
		frappe.db.set_value("BOM", name, "fm_recipe", None, update_modified=False)

	if recipes or boms:
		log(f"  unlinked {len(recipes)} recipe(s) and {len(boms)} BOM(s)")


def _retire_warehouses(log) -> None:
	"""Delete demo warehouses, or disable the ones that hold ledger history.

	A warehouse with Stock Ledger Entries cannot be deleted, and should not be:
	deleting stock history to tidy up a demo would be the wrong trade. Those
	warehouses are disabled instead, which takes them out of every selector
	while leaving the ledger intact.
	"""
	names = frappe.get_all(
		"Warehouse",
		filters={"warehouse_name": ("like", f"{PREFIX}%")},
		pluck="name",
		order_by="creation desc",
	)

	disabled = []
	for name in names:
		try:
			frappe.delete_doc("Warehouse", name, force=False, ignore_permissions=True)  # our own demo record
			log(f"  removed Warehouse {name}")
		except Exception:
			# Held by stock ledger history; disable rather than destroy it.
			frappe.db.set_value("Warehouse", name, "disabled", 1)
			disabled.append(name)

	if disabled:
		log(
			f"  kept {len(disabled)} warehouse(s) with stock ledger history, now disabled: "
			+ ", ".join(disabled)
		)


# -- setup -------------------------------------------------------------------


def _resolve_company(company: str | None) -> str:
	if company:
		if not frappe.db.exists("Company", company):
			frappe.throw(_("Company {0} does not exist.").format(frappe.bold(company)))
		return company

	# Prefer a company that calls itself a demo; otherwise the first one.
	demo = frappe.get_all(
		"Company", filters={"company_name": ("like", "%Demo%")}, pluck="name", order_by="name asc"
	)
	if demo:
		return demo[0]

	first = frappe.get_all("Company", pluck="name", order_by="name asc", limit=1)
	if not first:
		frappe.throw(_("No Company exists on this site."))

	return first[0]


def _enable_batch_setting(log) -> None:
	current = frappe.db.get_single_value("Stock Settings", BATCH_SETTING)
	if current:
		return

	frappe.db.set_single_value("Stock Settings", BATCH_SETTING, 1)
	# Remember that WE turned it on, so teardown can put it back.
	frappe.db.set_default(BATCH_SETTING_FLAG, "1")
	log("Enabled Stock Settings.enable_serial_and_batch_no_for_item (site-wide)")


def _ensure_warehouses(company: str, log) -> dict:
	"""Dedicated demo warehouses, so no existing warehouse is repurposed."""
	abbr = frappe.get_cached_value("Company", company, "abbr")
	wanted = {
		"stores": "Stores",
		"quarantine": "Quarantine",
		"rejected": "Rejected",
		"bulk": "Bulk Blend",
		"finished": "Finished Goods",
	}

	warehouses = {}
	for key, label in wanted.items():
		warehouse_name = f"{PREFIX} {label}"
		name = f"{warehouse_name} - {abbr}"
		if not frappe.db.exists("Warehouse", name):
			frappe.get_doc(
				{
					"doctype": "Warehouse",
					"warehouse_name": warehouse_name,
					"company": company,
					"is_group": 0,
				}
			).insert()
			log(f"  warehouse {name}")
		elif frappe.db.get_value("Warehouse", name, "disabled"):
			# Teardown disables rather than deletes a warehouse that holds
			# ledger history, so re-seeding has to switch it back on.
			frappe.db.set_value("Warehouse", name, "disabled", 0)
			frappe.clear_document_cache("Warehouse", name)
			log(f"  re-enabled warehouse {name}")

		warehouses[key] = name

	return warehouses


def _ensure_policy(company: str, warehouses: dict, log) -> None:
	values = {
		"quarantine_warehouse": warehouses["quarantine"],
		"rejected_warehouse": warehouses["rejected"],
		"bulk_warehouse": warehouses["bulk"],
		"finished_goods_warehouse": warehouses["finished"],
		"require_incoming_inspection": 0,
		"min_remaining_shelf_life_percent": 25,
		"near_expiry_alert_days": 90,
		"enforce_fefo": "Warn",
		"yield_variance_tolerance_percent": 4,
	}

	if frappe.db.exists("FM Manufacturing Policy", company):
		frappe.db.set_value("FM Manufacturing Policy", company, values)
		frappe.clear_document_cache("FM Manufacturing Policy", company)
		log("  policy updated")
		return

	frappe.get_doc({"doctype": "FM Manufacturing Policy", "company": company, **values}).insert()
	log("  policy created")


def _ensure_uoms(log) -> dict:
	for name in ("Kg", "Nos", "Gram"):
		if not frappe.db.exists("UOM", name):
			frappe.get_doc({"doctype": "UOM", "uom_name": name}).insert()

	if not frappe.db.exists("UOM Conversion Factor", {"from_uom": "Kg", "to_uom": "Gram"}):
		frappe.get_doc(
			{"doctype": "UOM Conversion Factor", "from_uom": "Kg", "to_uom": "Gram", "value": 1000}
		).insert()

	return {"kg": "Kg", "nos": "Nos", "gram": "Gram"}


def _ensure_parties(log) -> dict:
	supplier_name = f"{PREFIX} Spice Traders"
	if not frappe.db.exists("Supplier", supplier_name):
		frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": supplier_name,
				"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
			}
		).insert()
		log(f"  supplier {supplier_name}")

	customer_name = f"{PREFIX} Metro Retail"
	if not frappe.db.exists("Customer", customer_name):
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": customer_name,
				"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
				"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
			}
		).insert()
		log(f"  customer {customer_name}")

	return {"supplier": supplier_name, "customer": customer_name}


def _ensure_items(company: str, log) -> dict:
	group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")

	def make(code, name, uom, nature, batched=True, shelf_life=None, extra=None):
		item_code = f"{PREFIX} {code}"
		if not frappe.db.exists("Item", item_code):
			doc = frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item_code,
					"item_name": name,
					"item_group": group,
					"stock_uom": uom,
					"is_stock_item": 1,
					"has_batch_no": 1 if batched else 0,
					"create_new_batch": 1 if batched else 0,
					"batch_number_series": f"{PREFIX}-{code}-.###" if batched else None,
					"shelf_life_in_days": shelf_life,
					"fm_material_nature": nature,
					**(extra or {}),
				}
			)
			doc.insert()
			log(f"  item {item_code}")
		else:
			frappe.db.set_value("Item", item_code, {"fm_material_nature": nature, **(extra or {})})

		return item_code

	items = {
		"chilli": make("Red Chilli Powder", "Red Chilli Powder", "Kg", "Raw Material", shelf_life=540),
		"cumin": make("Cumin Powder", "Cumin Powder", "Kg", "Raw Material", shelf_life=540),
		"coriander": make("Coriander Powder", "Coriander Powder", "Kg", "Raw Material", shelf_life=540),
		"pouch50": make("Pouch 50g", "Pouch 50 g", "Nos", "Packaging Material", batched=False),
		"pouch100": make("Pouch 100g", "Pouch 100 g", "Nos", "Packaging Material", batched=False),
		"carton": make("Carton", "Shipping Carton", "Nos", "Packaging Material", batched=False),
	}

	items["blend"] = make(
		"Garam Masala Bulk", "Garam Masala Bulk Blend", "Kg", "Bulk Blend", shelf_life=365
	)
	items["sku50"] = make(
		"Garam Masala 50g",
		"Garam Masala 50 g Pack",
		"Nos",
		"Finished Good",
		shelf_life=365,
		extra={"fm_bulk_item": items["blend"], "fm_pack_size": 0.05, "fm_pack_uom": "Kg"},
	)
	items["sku100"] = make(
		"Garam Masala 100g",
		"Garam Masala 100 g Pack",
		"Nos",
		"Finished Good",
		shelf_life=365,
		extra={"fm_bulk_item": items["blend"], "fm_pack_size": 0.1, "fm_pack_uom": "Kg"},
	)

	return items


# -- the story ---------------------------------------------------------------


def _receive_raw_materials(company: str, warehouses: dict, items: dict, log) -> dict:
	"""Supplier lots into quarantine. Two lots per spice, to show split lots."""
	# Quantities cover all three blends with headroom: the three runs consume
	# 126 kg chilli and 84 kg cumin in total, and only released lots are
	# available to them.
	plan = [
		("chilli", "LOT-CH-2401", 120, 300, -40, 500),
		("chilli", "LOT-CH-2402", 60, 310, -10, 530),
		("cumin", "LOT-CU-2401", 140, 420, -35, 505),
		("cumin", "LOT-CU-2402", 40, 430, -5, 535),
		("coriander", "LOT-CO-2401", 50, 260, -20, 80),
	]

	lots = {}
	for key, lot_ref, qty, rate, made_days, shelf_days in plan:
		batch_id = f"{PREFIX}-{lot_ref}"
		item_code = items[key]

		if not frappe.db.exists("Batch", batch_id):
			frappe.get_doc({"doctype": "Batch", "batch_id": batch_id, "item": item_code}).insert()

		if not frappe.db.exists(
			"Stock Entry", {"remarks": f"{PREFIX} receipt {lot_ref}", "docstatus": 1}
		):
			entry = frappe.get_doc(
				{
					"doctype": "Stock Entry",
					"stock_entry_type": "Material Receipt",
					"purpose": "Material Receipt",
					"company": company,
					"remarks": f"{PREFIX} receipt {lot_ref}",
					"items": [
						{
							"item_code": item_code,
							"qty": qty,
							"t_warehouse": warehouses["quarantine"],
							"basic_rate": rate,
							"batch_no": batch_id,
							"use_serial_batch_fields": 1,
						}
					],
				}
			)
			entry.insert()
			entry.submit()
			log(f"  received {qty} of {item_code} as {batch_id}")

		# Supplier identity and dates, applied after the receipt so an
		# already-expired lot can exist without blocking its own arrival.
		values = {
			"fm_supplier_lot_no": lot_ref,
			"supplier": f"{PREFIX} Spice Traders",
			"manufacturing_date": add_days(today(), made_days),
			"expiry_date": add_days(today(), made_days + shelf_days),
		}

		# Only quarantine a batch that has no decision yet. Re-running must not
		# undo a release or a rejection - the same rule the Purchase Receipt
		# override follows when stamping received stock.
		if not frappe.db.get_value("Batch", batch_id, "fm_quality_status"):
			values["fm_quality_status"] = "Quarantine"

		frappe.db.set_value("Batch", batch_id, values)
		frappe.clear_document_cache("Batch", batch_id)
		lots[lot_ref] = batch_id

	return lots


def _release_lots(company: str, lots: dict, log) -> None:
	"""Release most lots; leave two for the pending-QC queue, reject one."""
	decisions = {
		"LOT-CH-2401": "Release",
		"LOT-CH-2402": "Release",
		"LOT-CU-2401": "Release",
		"LOT-CU-2402": None,  # stays in quarantine, so the QC queue is not empty
		"LOT-CO-2401": "Reject",
	}

	for lot_ref, decision in decisions.items():
		batch = lots.get(lot_ref)
		if not batch or not decision:
			continue

		if frappe.db.exists("FM Batch Release", {"batch": batch, "docstatus": 1}):
			continue

		doc = frappe.get_doc(
			{
				"doctype": "FM Batch Release",
				"batch": batch,
				"company": company,
				"decision": decision,
				"reason": "Moisture above specification" if decision == "Reject" else None,
			}
		)
		doc.insert()
		doc.submit()
		log(f"  {decision.lower()}d {batch}")


def _move_decided_stock(company: str, warehouses: dict, items: dict, lots: dict, log) -> None:
	"""Move stock out of quarantine once a decision has been made.

	Releasing a batch is a decision, not a movement - the stock stays where it
	is until somebody shifts it. Seeding that step matters: without it the
	blending run draws from the quarantine warehouse and the quality gate
	refuses it, which is exactly what happened the first time this ran.
	"""
	moves = {
		"LOT-CH-2401": "stores",
		"LOT-CH-2402": "stores",
		"LOT-CU-2401": "stores",
		"LOT-CO-2401": "rejected",
		# LOT-CU-2402 stays in quarantine: it has no decision yet.
	}

	for lot_ref, destination in moves.items():
		batch = lots.get(lot_ref)
		if not batch:
			continue

		marker = f"{PREFIX} move {lot_ref}"
		if frappe.db.exists("Stock Entry", {"remarks": marker, "docstatus": 1}):
			continue

		qty = _batch_qty(batch, warehouses["quarantine"])
		if qty <= 0:
			continue

		item_code = frappe.db.get_value("Batch", batch, "item")
		entry = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Transfer",
				"purpose": "Material Transfer",
				"company": company,
				"remarks": marker,
				"items": [
					{
						"item_code": item_code,
						"qty": qty,
						"s_warehouse": warehouses["quarantine"],
						"t_warehouse": warehouses[destination],
						"batch_no": batch,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		entry.insert()
		entry.submit()
		log(f"  moved {batch} to {warehouses[destination]}")


def _batch_qty(batch: str, warehouse: str) -> float:
	from food_manufacturing.stock_levels import get_batch_quantities

	return flt(get_batch_quantities([batch], [warehouse]).get(batch))


def _approve_recipe(company: str, items: dict, uoms: dict, log) -> str:
	existing = frappe.get_all(
		"FM Recipe",
		filters={"item": items["blend"], "company": company, "docstatus": 1, "status": "Approved"},
		pluck="name",
		order_by="revision desc",
		limit=1,
	)
	if existing:
		return existing[0]

	doc = frappe.get_doc(
		{
			"doctype": "FM Recipe",
			"item": items["blend"],
			"company": company,
			"batch_size": 100,
			"batch_uom": uoms["kg"],
			"ingredients": [
				{"item_code": items["chilli"], "percentage": 60, "uom": uoms["kg"]},
				{"item_code": items["cumin"], "percentage": 40, "uom": uoms["kg"]},
			],
		}
	)
	doc.insert()
	doc.submit()
	log(f"  recipe {doc.name} approved -> BOM {doc.bom}")
	return doc.name


def _run_blending(company: str, warehouses: dict, items: dict, recipe: str, log) -> list:
	"""Three blends: two healthy, one with a yield outside tolerance."""
	from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

	bom = frappe.db.get_value("FM Recipe", recipe, "bom")
	runs = [("BULK-001", 100, 3), ("BULK-002", 60, 1.5), ("BULK-003", 50, 4.5)]

	blends = []
	for batch_ref, qty, loss in runs:
		batch_id = f"{PREFIX}-{batch_ref}"
		if frappe.db.exists("Batch", batch_id):
			blends.append(batch_id)
			continue

		order = frappe.get_doc(
			{
				"doctype": "Work Order",
				"production_item": items["blend"],
				"bom_no": bom,
				"qty": qty,
				"company": company,
				"fg_warehouse": warehouses["bulk"],
				"wip_warehouse": warehouses["stores"],
				# Released stock only: the quality gate would refuse quarantine.
				"source_warehouse": warehouses["stores"],
				"use_multi_level_bom": 0,
				"skip_transfer": 1,
			}
		)
		order.insert()
		order.submit()

		if not frappe.db.exists("Batch", batch_id):
			frappe.get_doc({"doctype": "Batch", "batch_id": batch_id, "item": items["blend"]}).insert()

		entry = frappe.get_doc(make_stock_entry(order.name, "Manufacture", qty))
		entry.remarks = f"{PREFIX} blend {batch_ref}"
		for row in entry.items:
			row.use_serial_batch_fields = 1
			if row.item_code == items["blend"] and row.t_warehouse:
				row.batch_no = batch_id
				row.qty = qty - loss
				row.transfer_qty = qty - loss
		entry.process_loss_qty = loss
		entry.insert()
		entry.submit()

		frappe.db.set_value(
			"Batch",
			batch_id,
			{
				"manufacturing_date": nowdate(),
				"expiry_date": add_days(today(), 365),
				"fm_quality_status": "Released",
			},
		)
		frappe.clear_document_cache("Batch", batch_id)

		order.reload()
		log(f"  blended {batch_ref}: {order.produced_qty} kg, {loss} kg loss, yield {order.fm_actual_yield_percent}%")
		blends.append(batch_id)

	return blends


def _run_packaging(company: str, warehouses: dict, items: dict, uoms: dict, blends: list, log) -> dict:
	"""Pack the first blend into two sizes, leaving bulk on hand."""
	from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

	_receive_packaging(company, warehouses, items, log)

	packs = {}
	plan = [
		("sku50", "PACK-50G-001", 1000, items["pouch50"], 1000, 10, 50),
		("sku100", "PACK-100G-001", 400, items["pouch100"], 400, 4, 40),
	]

	for key, batch_ref, qty, pouch, pouch_qty, cartons, bulk_kg in plan:
		batch_id = f"{PREFIX}-{batch_ref}"
		if frappe.db.exists("Batch", batch_id):
			packs[key] = batch_id
			continue

		bom = _ensure_packaging_bom(
			company, items[key], qty, uoms, items["blend"], bulk_kg, pouch, pouch_qty,
			items["carton"], cartons,
		)

		order = frappe.get_doc(
			{
				"doctype": "Work Order",
				"production_item": items[key],
				"bom_no": bom,
				"qty": qty,
				"company": company,
				"fg_warehouse": warehouses["finished"],
				"wip_warehouse": warehouses["stores"],
				"source_warehouse": warehouses["bulk"],
				"use_multi_level_bom": 0,
				"skip_transfer": 1,
			}
		)
		order.insert()
		order.submit()

		if not frappe.db.exists("Batch", batch_id):
			frappe.get_doc({"doctype": "Batch", "batch_id": batch_id, "item": items[key]}).insert()

		entry = frappe.get_doc(make_stock_entry(order.name, "Manufacture", qty))
		entry.remarks = f"{PREFIX} pack {batch_ref}"
		for row in entry.items:
			row.use_serial_batch_fields = 1
			if row.item_code == items[key] and row.t_warehouse:
				row.batch_no = batch_id
			if row.item_code == items["blend"] and row.s_warehouse:
				row.batch_no = blends[0]
		entry.insert()
		entry.submit()

		frappe.db.set_value(
			"Batch",
			batch_id,
			{
				"manufacturing_date": nowdate(),
				"expiry_date": add_days(today(), 330),
				"fm_quality_status": "Released",
			},
		)
		frappe.clear_document_cache("Batch", batch_id)
		log(f"  packed {batch_ref}: {qty} packs from {blends[0]}")
		packs[key] = batch_id

	return packs


def _receive_packaging(company: str, warehouses: dict, items: dict, log) -> None:
	plan = [("pouch50", 3000, 2), ("pouch100", 1200, 3), ("carton", 200, 25)]

	for key, qty, rate in plan:
		marker = f"{PREFIX} packaging {key}"
		if frappe.db.exists("Stock Entry", {"remarks": marker, "docstatus": 1}):
			continue

		entry = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"purpose": "Material Receipt",
				"company": company,
				"remarks": marker,
				"items": [
					{
						"item_code": items[key],
						"qty": qty,
						"t_warehouse": warehouses["bulk"],
						"basic_rate": rate,
					}
				],
			}
		)
		entry.insert()
		entry.submit()
		log(f"  received {qty} {items[key]}")


def _ensure_packaging_bom(company, sku, qty, uoms, blend, bulk_kg, pouch, pouch_qty, carton, cartons):
	existing = frappe.get_all(
		"BOM", filters={"item": sku, "docstatus": 1}, pluck="name", order_by="creation desc", limit=1
	)
	if existing:
		return existing[0]

	bom = frappe.get_doc(
		{
			"doctype": "BOM",
			"item": sku,
			"company": company,
			"quantity": qty,
			"uom": uoms["nos"],
			"currency": frappe.get_cached_value("Company", company, "default_currency"),
			"is_active": 1,
			"is_default": 1,
			"items": [
				{"item_code": blend, "qty": bulk_kg, "uom": uoms["kg"]},
				{"item_code": pouch, "qty": pouch_qty, "uom": uoms["nos"]},
				{"item_code": carton, "qty": cartons, "uom": uoms["nos"]},
			],
		}
	)
	bom.insert()
	bom.submit()
	return bom.name


def _dispatch(company: str, warehouses: dict, items: dict, parties: dict, packs: dict, log) -> None:
	"""Ship some of each pack size, so a sold batch traces back to its lots."""
	if not packs:
		return

	if frappe.db.exists("Delivery Note", {"customer": parties["customer"], "docstatus": 1}):
		return

	rows = []
	for key, qty, rate in (("sku50", 400, 60), ("sku100", 150, 110)):
		batch = packs.get(key)
		if not batch:
			continue
		rows.append(
			{
				"item_code": items[key],
				"qty": qty,
				"rate": rate,
				"warehouse": warehouses["finished"],
				"batch_no": batch,
				"use_serial_batch_fields": 1,
			}
		)

	if not rows:
		return

	note = frappe.get_doc(
		{
			"doctype": "Delivery Note",
			"company": company,
			"customer": parties["customer"],
			"items": rows,
		}
	)
	note.insert()
	note.submit()
	log(f"  dispatched {note.name} to {parties['customer']}")


# -- helpers -----------------------------------------------------------------


def _add_ageing_stock(company: str, warehouses: dict, items: dict, lots: dict, log) -> None:
	"""A few batches close to expiry, so the expiry horizon is not empty.

	Received first and dated afterwards: ERPNext refuses to receive stock into
	an already-expired batch, which is the correct rule and the reason the
	dates are applied as a second step.
	"""
	plan = [
		("sku50", "AGED-50G-001", 240, 6, 55),
		("sku100", "AGED-100G-001", 90, 24, 95),
		("blend", "AGED-BULK-001", 35, 70, 190),
	]

	for key, batch_ref, qty, days_left, rate in plan:
		batch_id = f"{PREFIX}-{batch_ref}"
		marker = f"{PREFIX} ageing {batch_ref}"

		if not frappe.db.exists("Batch", batch_id):
			frappe.get_doc({"doctype": "Batch", "batch_id": batch_id, "item": items[key]}).insert()

		if not frappe.db.exists("Stock Entry", {"remarks": marker, "docstatus": 1}):
			warehouse = warehouses["bulk"] if key == "blend" else warehouses["finished"]
			entry = frappe.get_doc(
				{
					"doctype": "Stock Entry",
					"stock_entry_type": "Material Receipt",
					"purpose": "Material Receipt",
					"company": company,
					"remarks": marker,
					"items": [
						{
							"item_code": items[key],
							"qty": qty,
							"t_warehouse": warehouse,
							"basic_rate": rate,
							"batch_no": batch_id,
							"use_serial_batch_fields": 1,
						}
					],
				}
			)
			entry.insert()
			entry.submit()

		frappe.db.set_value(
			"Batch",
			batch_id,
			{
				"fm_quality_status": "Released",
				"manufacturing_date": add_days(today(), days_left - 365),
				"expiry_date": add_days(today(), days_left),
			},
		)
		frappe.clear_document_cache("Batch", batch_id)
		log(f"  ageing stock {batch_id}: {qty} units, expires in {days_left} days")

	# The undecided cumin lot is also approaching expiry, which is exactly the
	# situation a quality manager needs surfacing.
	held = lots.get("LOT-CU-2402")
	if held:
		frappe.db.set_value(
			"Batch",
			held,
			{"manufacturing_date": add_days(today(), -340), "expiry_date": add_days(today(), 25)},
		)
		frappe.clear_document_cache("Batch", held)


def _summarise(company: str, items: dict, blends: list, packs: dict) -> dict:
	from food_manufacturing.stock_levels import get_batch_quantities

	warehouses = frappe.get_all(
		"Warehouse", filters={"company": company}, pluck="name", order_by="name asc"
	)
	bulk_left = sum(flt(q) for q in get_batch_quantities(blends, warehouses).values())

	return {
		"company": company,
		"blend batches": len(blends),
		"pack batches": len(packs),
		"bulk on hand (kg)": round(bulk_left, 2),
	}


def _force_delete(doctype: str, name: str, log) -> None:
	try:
		doc = frappe.get_doc(doctype, name)
		if getattr(doc, "docstatus", 0) == 1:
			doc.cancel()
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)  # teardown of our own demo records
		log(f"  removed {doctype} {name}")
	except Exception as exc:
		log(f"  could not remove {doctype} {name}: {exc}")


def _logger(verbose: bool):
	def log(message: str) -> None:
		if verbose:
			frappe.publish_progress(0, title=message)
			print(message)  # noqa: T201 - this is a CLI seeding tool

	return log

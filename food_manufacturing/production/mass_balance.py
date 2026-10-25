"""Where a lot went, and whether the transformation it fed adds up.

Two questions, deliberately kept apart because only one of them can fail.

**Disposition** — how much of a lot was consumed, issued, dispatched and is
still on hand. For one batch inside one company the stock ledger guarantees
``inward - outward == on hand``, so the identity itself proves nothing: a
balance that always balances is not a control. What the ledger does *not* tell
you is *which* destination took the stock, and that breakdown is what an
investigator acts on.

**Transformation** — the output of a blend is a different item, with a
different batch, from its inputs. No ledger identity constrains the two, so
this is the figure that genuinely *can* disagree: 100 kg of ingredients
reported as 110 kg of blend is visible here and nowhere else. In a spice plant
that is the shape extension, a mis-keyed output or a double-counted input
takes.

Nothing here is stored. Every figure is derived from submitted transactions, so
it cannot drift from the ledger — the same rule `genealogy.py` follows.

This module reports; it does not judge. ``flagged`` means "worth a human
looking", measured against the company's own yield tolerance. Calling a
discrepancy fraud is not a claim this app has any standing to make.
"""

import frappe
from frappe import _
from frappe.utils import flt

from food_manufacturing.food_manufacturing_setup.doctype.fm_manufacturing_policy.fm_manufacturing_policy import (
	get_policy_if_any,
)
from food_manufacturing.production.genealogy import (
	get_batch_movements,
	get_consuming_work_orders,
	get_work_order_batches,
)
from food_manufacturing.stock_levels import get_batch_balances

#: Stock Entry purposes that only move stock between this company's own
#: warehouses. Both sides are skipped: a quarantine-to-stores transfer puts the
#: same kilograms through the ledger twice, once out and once in, and counting
#: either side reports stock that never entered or left the plant. This was the
#: first thing the demo data caught - a 120 kg lot read as 240 kg received.
INTERNAL_PURPOSES = (
	"Material Transfer",
	"Material Transfer for Manufacture",
	"Send to Subcontractor",
)

#: Purposes where a Stock Entry is a production step: negative is consumption
#: into a run, positive is that run's output.
PRODUCTION_PURPOSES = (
	"Manufacture",
	"Repack",
	"Material Consumption for Manufacture",
)


def get_lot_disposition(batch: str, company: str) -> dict:
	"""Account for every unit of ``batch`` inside ``company``.

	Quantities are in the batch item's own stock UOM. ``residual`` is what the
	breakdown could not place; see the module docstring for why it is expected
	to be zero and what a non-zero value means.
	"""
	info = frappe.db.get_value("Batch", batch, ["item", "batch_id"], as_dict=True)
	if not info:
		frappe.throw(_("Batch {0} does not exist.").format(frappe.bold(batch)))

	stock_uom = frappe.db.get_value("Item", info.item, "stock_uom")

	received = 0.0
	produced = 0.0
	consumed = 0.0
	issued = 0.0

	entries = get_batch_movements({batch}, company, "Stock Entry")
	if entries:
		purposes = {
			row.name: row.purpose
			for row in frappe.get_all(
				"Stock Entry",
				filters={"name": ("in", sorted({row["voucher_no"] for row in entries}))},
				fields=["name", "purpose"],
				order_by="name asc",
			)
		}
		for row in entries:
			purpose = purposes.get(row["voucher_no"])
			if purpose in INTERNAL_PURPOSES:
				continue

			qty = flt(row["qty"])
			if qty > 0:
				if purpose in PRODUCTION_PURPOSES:
					produced += qty
				else:
					received += qty
			elif purpose in PRODUCTION_PURPOSES:
				consumed += abs(qty)
			elif purpose == "Material Issue":
				issued += abs(qty)

	# A Purchase Receipt brings purchased stock in; a purchase return comes back
	# negative and nets itself off what was received.
	received += sum(flt(row["qty"]) for row in get_batch_movements({batch}, company, "Purchase Receipt"))

	# Delivery Notes keep the ledger's sign, so a sales return is positive and
	# nets itself off the dispatched total.
	dispatched = -sum(flt(row["qty"]) for row in get_batch_movements({batch}, company, "Delivery Note"))

	# A reconciliation is neither a receipt nor a consumption: it is somebody
	# correcting the books, and it belongs in its own line rather than hidden
	# inside one of the others.
	adjusted = sum(
		flt(row["qty"]) for row in get_batch_movements({batch}, company, "Stock Reconciliation")
	)

	by_warehouse = _on_hand_by_warehouse(batch, company)
	on_hand = sum(by_warehouse.values())

	policy = get_policy_if_any(company)
	rejected_warehouse = policy.rejected_warehouse if policy else None

	inward = received + produced
	placed = consumed + issued + dispatched + on_hand

	return {
		"batch_no": batch,
		"item_code": info.item,
		"stock_uom": stock_uom,
		"company": company,
		"received_qty": flt(received),
		"produced_qty": flt(produced),
		"inward_qty": flt(inward),
		"consumed_in_production": flt(consumed),
		"issued_qty": flt(issued),
		"dispatched_qty": flt(dispatched),
		"adjusted_qty": flt(adjusted),
		"on_hand_qty": flt(on_hand),
		# Quarantined and rejected stock is still on hand; naming the rejected
		# share separately is what tells an investigator it is already contained.
		"in_rejected_warehouse": flt(by_warehouse.get(rejected_warehouse, 0.0)),
		"on_hand_by_warehouse": [
			{"warehouse": warehouse, "qty": flt(qty)}
			for warehouse, qty in sorted(by_warehouse.items())
		],
		"residual_qty": flt(inward + adjusted - placed),
	}


def _on_hand_by_warehouse(batch: str, company: str) -> dict:
	"""Current balance of ``batch`` per warehouse of ``company``, zeroes dropped."""
	warehouses = frappe.get_all(
		"Warehouse",
		filters={"company": company, "is_group": 0},
		pluck="name",
		order_by="name asc",
	)
	if not warehouses:
		return {}

	balances = get_batch_balances([batch], warehouses)
	return {
		warehouse: flt(qty)
		for (_batch_no, warehouse), qty in balances.items()
		if flt(qty)
	}


def get_chain_transformation(batch: str, company: str) -> list:
	"""Every production step this lot fed, with input against output.

	One row per consuming Work Order. ``flagged`` is set when the step's output
	plus its declared losses exceeds what went in by more than the company's
	yield tolerance — output cannot exceed input, so that is a data or a
	process problem either way.

	The loop over Work Orders reads the ledger per order, which is bounded by
	the number of orders that consumed this one lot — the same bounded
	traversal `genealogy.trace_backward` uses.
	"""
	orders = get_consuming_work_orders(batch)
	if not orders:
		return []

	policy = get_policy_if_any(company)
	tolerance = flt(policy.yield_variance_tolerance_percent) if policy else 0.0

	headers = {
		row.name: row
		for row in frappe.get_all(
			"Work Order",
			filters={"name": ("in", sorted(orders)), "company": company},
			fields=[
				"name",
				"production_item",
				"qty",
				"produced_qty",
				"process_loss_qty",
				"fm_actual_input_qty",
				"fm_actual_yield_percent",
				"fm_byproduct_qty",
				"fm_yield_flagged",
				"fm_yield_basis",
			],
			order_by="name asc",
		)
	}

	uoms = _item_uoms(orders)

	rows = []
	for order in sorted(orders):
		header = headers.get(order)
		if not header:
			# A Work Order of another company: not this company's balance to report.
			continue

		movements = get_work_order_batches(order)
		lot_input = sum(
			flt(row["qty"]) for row in movements["consumed"] if row["batch_no"] == batch
		)
		total_input = sum(flt(row["qty"]) for row in movements["consumed"])
		total_output = sum(flt(row["qty"]) for row in movements["produced"])

		uom, basis = _comparable_uom(movements, uoms)
		overrun = total_output + flt(header.process_loss_qty) - total_input
		# A tolerance in percent of the input, so it scales with the run size.
		allowed = abs(total_input) * tolerance / 100.0

		rows.append(
			{
				"work_order": order,
				"production_item": header.production_item,
				"lot_input_qty": flt(lot_input),
				"total_input_qty": flt(total_input),
				"total_output_qty": flt(total_output),
				"process_loss_qty": flt(header.process_loss_qty),
				"byproduct_qty": flt(header.fm_byproduct_qty),
				"produced_qty": flt(header.produced_qty),
				"actual_yield_percent": flt(header.fm_actual_yield_percent),
				"yield_basis": header.fm_yield_basis,
				"comparable": bool(uom),
				"balance_uom": uom,
				"balance_basis": basis,
				"overrun_qty": flt(overrun) if uom else None,
				# Two reasons not to flag. Mixed UOMs: a packaging run consumes
				# kilograms of bulk and produces a count of packs, so output
				# minus input is arithmetic on incompatible units - the same
				# honesty rule `yield_tracking.py` follows. No input yet: an
				# unstarted run is not a discrepancy.
				"flagged": bool(uom) and bool(total_input) and overrun > allowed,
			}
		)

	return rows


def _item_uoms(orders) -> dict:
	"""Stock UOM of every item any of ``orders`` touched, in one query.

	Read up front rather than per row: the comparison needs them for both
	sides of every step, and fetching inside the loop would be a query per
	item.
	"""
	items = frappe.get_all(
		"Work Order Item",
		filters={"parent": ("in", sorted(orders))},
		pluck="item_code",
	)
	items += frappe.get_all(
		"Work Order",
		filters={"name": ("in", sorted(orders))},
		pluck="production_item",
	)
	if not items:
		return {}

	return {
		row.name: row.stock_uom
		for row in frappe.get_all(
			"Item",
			filters={"name": ("in", sorted(set(items)))},
			fields=["name", "stock_uom"],
			order_by="name asc",
		)
	}


def _comparable_uom(movements: dict, uoms: dict):
	"""The UOM an input/output balance may be struck in, or None and why.

	Subtracting output from input only means something when every quantity on
	both sides is in the same unit. A packaging run consuming kilograms of bulk
	to produce a count of packs has no such unit, and reporting "950 over" for
	it would be a number nobody should trust - exactly what
	``yield_tracking.fm_yield_basis`` exists to refuse.
	"""
	sides = [row["item_code"] for row in movements["consumed"]] + [
		row["item_code"] for row in movements["produced"]
	]
	if not sides:
		return None, _("No consumption or output recorded yet")

	units = {uoms.get(item) for item in sides}
	if None in units:
		return None, _("An item on this step has no stock UOM")

	if len(units) > 1:
		return None, _("Input and output are in different units ({0})").format(
			", ".join(sorted(unit for unit in units if unit))
		)

	return units.pop(), None


def get_mass_balance(batch: str, company: str) -> dict:
	"""Disposition and transformation for one lot, with a single verdict.

	``flagged`` is true when any transformation step overran its input, or when
	the disposition left a residual it could not place. Both mean "a person
	should look", not "something is wrong".
	"""
	disposition = get_lot_disposition(batch, company)
	transformation = get_chain_transformation(batch, company)

	# The residual is compared against the lot's own size rather than to zero:
	# stock quantities carry float rounding, and a 0.0001 kg artefact is not a
	# finding.
	residual_material = abs(disposition["residual_qty"]) > max(
		0.01, abs(disposition["inward_qty"]) * 0.001
	)

	return {
		"disposition": disposition,
		"transformation": transformation,
		"flagged": residual_material or any(row["flagged"] for row in transformation),
		"residual_material": residual_material,
	}

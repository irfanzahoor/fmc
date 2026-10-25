"""Supplier Scorecard variables this app contributes.

ERPNext's Supplier Scorecard scores what happened on the *purchase*. It has no
way to know what the lab decided afterwards, which in this app is held on
`Batch.fm_quality_status` and written only by `FM Batch Release`.

`Supplier Scorecard Variable.path` accepts a dotted path and ERPNext resolves it
with `import_string_path`, so an app can contribute variables without a scoring
engine of its own. The registered paths point at
:mod:`food_manufacturing.scorecard_variables`, which explains why they are only
one level deep. A plant then uses them in its own Supplier Scorecard Criteria
exactly like the built-in ones — which is the point: this app supplies the
*measurement* and leaves the *judgement* to the plant.

Created in code rather than exported as fixtures, for the same reason the custom
fields are: `Supplier Scorecard Variable` has no `module` field, so a scoped
fixture filter cannot express "ours", and a name-based filter would silently
stop exporting a variable the moment one was renamed.
"""

import frappe

#: ``param_name`` is what a Criteria formula refers to, so these names are part
#: of the plant's configuration and must not be renamed casually.
FM_VARIABLES = (
	{
		"variable_label": "FM Lots Received",
		"param_name": "fm_lots_received",
		"path": "food_manufacturing.scorecard_variables.get_fm_lots_received",
		"description": (
			"Number of lots received from the supplier in the period, counted from the "
			"batches the stock ledger brought in."
		),
	},
	{
		"variable_label": "FM Received Qty",
		"param_name": "fm_received_qty",
		"path": "food_manufacturing.scorecard_variables.get_fm_received_qty",
		"description": (
			"Quantity received from the supplier in the period, in each item's stock UOM, "
			"excluding the inward leg of internal warehouse transfers."
		),
	},
	{
		"variable_label": "FM QC Rejected Qty",
		"param_name": "fm_qc_rejected_qty",
		"path": "food_manufacturing.scorecard_variables.get_fm_qc_rejected_qty",
		"description": (
			"Quantity rejected by the plant's own quality decision. Distinct from ERPNext's "
			"rejected_qty, which is what was marked at the receiving gate: this is what the "
			"lab decided afterwards, which is usually days later."
		),
	},
	{
		"variable_label": "FM Usable Qty",
		"param_name": "fm_usable_qty",
		"path": "food_manufacturing.scorecard_variables.get_fm_usable_qty",
		"description": (
			"Quantity that survived the quality decision: received less rejected. A lot still "
			"on hold is counted as usable, because holding is not a decision against it."
		),
	},
)


def ensure_scorecard_variables() -> None:
	"""Create or refresh this app's scorecard variables. Safe to re-run.

	The description and the path are updated in place on an existing record, so
	a corrected path reaches a site that already has the variable. ``is_custom``
	is set because these are not ERPNext's own built-ins.
	"""
	if not frappe.db.exists("DocType", "Supplier Scorecard Variable"):
		# Buying may not be installed on every site this app runs on.
		return

	for variable in FM_VARIABLES:
		values = {**variable, "is_custom": 1}

		if frappe.db.exists("Supplier Scorecard Variable", variable["variable_label"]):
			doc = frappe.get_doc("Supplier Scorecard Variable", variable["variable_label"])
			doc.update(values)
			doc.save()
			continue

		frappe.get_doc({"doctype": "Supplier Scorecard Variable", **values}).insert()

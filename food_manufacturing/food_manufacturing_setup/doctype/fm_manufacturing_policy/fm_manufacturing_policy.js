// Client script is UX only: every rule below is also enforced in
// fm_manufacturing_policy.py.

frappe.ui.form.on("FM Manufacturing Policy", {
	setup(frm) {
		const warehouse_fields = [
			"quarantine_warehouse",
			"rejected_warehouse",
			"bulk_warehouse",
			"packaging_warehouse",
			"finished_goods_warehouse",
		];

		// Only offer leaf warehouses of the selected company.
		warehouse_fields.forEach((fieldname) => {
			frm.set_query(fieldname, () => ({
				filters: {
					company: frm.doc.company,
					is_group: 0,
				},
			}));
		});
	},

	company(frm) {
		// Warehouses of the previous company are no longer valid choices.
		const warehouse_fields = [
			"quarantine_warehouse",
			"rejected_warehouse",
			"bulk_warehouse",
			"packaging_warehouse",
			"finished_goods_warehouse",
		];

		warehouse_fields.forEach((fieldname) => frm.set_value(fieldname, null));
	},

	enforce_fefo(frm) {
		if (frm.doc.enforce_fefo === "Off") {
			frappe.show_alert({
				message: __("FEFO recommendations will still be shown but never enforced."),
				indicator: "orange",
			});
		}
	},
});

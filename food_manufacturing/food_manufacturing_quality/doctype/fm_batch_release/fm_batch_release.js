// Client script is UX only: every rule below is also enforced in
// fm_batch_release.py.

frappe.ui.form.on("FM Batch Release", {
	setup(frm) {
		// A rejected batch is terminal, and a disabled batch cannot be decided on.
		frm.set_query("batch", () => ({
			filters: {
				disabled: 0,
			},
		}));

		frm.set_query("quality_inspection", () => ({
			filters: {
				docstatus: 1,
				...(frm.doc.item_code ? { item_code: frm.doc.item_code } : {}),
			},
		}));
	},

	refresh(frm) {
		frm.toggle_reqd("reason", frm.doc.decision && frm.doc.decision !== "Release");

		if (frm.doc.docstatus === 1 && frm.doc.batch) {
			frm.add_custom_button(__("View Batch"), () =>
				frappe.set_route("Form", "Batch", frm.doc.batch)
			);
		}
	},

	decision(frm) {
		frm.toggle_reqd("reason", frm.doc.decision && frm.doc.decision !== "Release");
	},

	batch(frm) {
		if (!frm.doc.batch) {
			return;
		}

		// Show the current status so the operator is not guessing at the transition.
		frappe.db.get_value("Batch", frm.doc.batch, "fm_quality_status").then(({ message }) => {
			const status = (message && message.fm_quality_status) || __("not quality-managed");
			frm.dashboard.clear_headline();
			frm.dashboard.set_headline(__("Current quality status: {0}", [status]));
		});
	},
});

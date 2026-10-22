// Client script is UX only: percentage totals, UOM conversion and approval
// rules are all enforced in fm_recipe.py.

frappe.ui.form.on("FM Recipe", {
	setup(frm) {
		frm.set_query("item", () => ({
			filters: {
				is_stock_item: 1,
				disabled: 0,
			},
		}));

		frm.set_query("item_code", "ingredients", () => ({
			filters: {
				is_stock_item: 1,
				disabled: 0,
			},
		}));
	},

	refresh(frm) {
		show_total(frm);

		if (frm.doc.docstatus === 1 && frm.doc.bom) {
			frm.add_custom_button(__("View BOM"), () =>
				frappe.set_route("Form", "BOM", frm.doc.bom)
			);
		}
	},

	batch_size(frm) {
		recalculate(frm);
	},

	batch_uom(frm) {
		recalculate(frm);
	},
});

frappe.ui.form.on("FM Recipe Ingredient", {
	percentage(frm) {
		recalculate(frm);
	},

	uom(frm) {
		recalculate(frm);
	},

	ingredients_remove(frm) {
		recalculate(frm);
	},
});

// Mirrors set_quantities() in the controller so the operator sees the effect
// before saving. The server recomputes it regardless.
function recalculate(frm) {
	const batch_size = flt(frm.doc.batch_size);

	(frm.doc.ingredients || []).forEach((row) => {
		const factor = flt(row.conversion_factor) || 1;
		row.qty = flt((batch_size * flt(row.percentage)) / 100) * factor;
	});

	frm.refresh_field("ingredients");
	show_total(frm);
}

function show_total(frm) {
	// The formula is permlevel-protected: a user without access has no
	// ingredient rows at all, so there is nothing to total.
	if (!frm.doc.ingredients) {
		return;
	}

	const total = (frm.doc.ingredients || []).reduce(
		(sum, row) => sum + flt(row.percentage),
		0
	);

	frm.set_value("total_percentage", total);

	frm.dashboard.clear_headline();
	if (Math.abs(total - 100) > 0.01) {
		frm.dashboard.set_headline(
			__("Percentages total {0}% — must total 100%", [format_number(total, null, 2)])
		);
	}
}

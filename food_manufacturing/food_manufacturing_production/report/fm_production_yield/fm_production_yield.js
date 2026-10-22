// Filters only: all figures come from the server.
frappe.query_reports["FM Production Yield"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "production_item",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "flagged_only",
			label: __("Variance Flagged Only"),
			fieldtype: "Check",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		// Draw attention to a flagged run without relying on colour alone:
		// the Flagged column stays visible and sortable.
		if (data && data.fm_yield_flagged && column.fieldname === "fm_yield_variance_percent") {
			value = `<span class="text-danger font-weight-bold">${value}</span>`;
		}

		return value;
	},
};

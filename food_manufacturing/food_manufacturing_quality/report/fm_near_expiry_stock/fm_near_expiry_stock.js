frappe.query_reports["FM Near Expiry Stock"] = {
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
			fieldname: "within_days",
			label: __("Within Days"),
			fieldtype: "Int",
			description: __("Leave blank to use the company's configured alert horizon."),
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		// Already expired is a different problem from expiring soon. The
		// Days to Expiry number stays visible, so this is emphasis, not the
		// only signal.
		if (data && column.fieldname === "days_to_expiry") {
			if (data.days_to_expiry < 0) {
				value = `<span class="text-danger font-weight-bold">${value}</span>`;
			} else if (data.days_to_expiry <= 7) {
				value = `<span class="text-warning font-weight-bold">${value}</span>`;
			}
		}

		return value;
	},
};

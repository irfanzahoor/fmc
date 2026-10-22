frappe.query_reports["FM Pending Batch Release"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "quality_status",
			label: __("Quality Status"),
			fieldtype: "Select",
			options: ["", "Quarantine", "Hold"],
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		// Long waits are the point of this queue, so make them legible.
		if (data && column.fieldname === "days_waiting" && data.days_waiting > 7) {
			value = `<span class="text-danger font-weight-bold">${value}</span>`;
		}

		return value;
	},
};

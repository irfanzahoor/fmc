// Filters for the recall investigation report.
frappe.query_reports["FM Recall Investigation"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "batch",
			label: __("Batch"),
			fieldtype: "Link",
			options: "Batch",
			reqd: 1,
		},
		{
			fieldname: "section",
			label: __("Show"),
			fieldtype: "Select",
			options: ["", "Affected batches", "Stock on hand", "Deliveries"].join("\n"),
			default: "",
		},
	],
};

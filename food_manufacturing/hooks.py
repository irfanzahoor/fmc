app_name = "food_manufacturing"
app_title = "Food Manufacturing"
app_publisher = "Irfan Zahoor"
app_description = (
	"Spice and masala manufacturing on ERPNext: supplier lots, approved recipes, "
	"bulk blending, packaging and batch traceability"
)
app_email = "support@nextash.com"
app_license = "mit"
required_apps = ["frappe/erpnext"]

# Installation
# ------------
# Roles are created in before_install so that DocType permissions referencing
# them resolve during the DocType sync that follows.
before_install = "food_manufacturing.setup.install.before_install"
after_install = "food_manufacturing.setup.install.after_install"
after_migrate = "food_manufacturing.setup.install.after_migrate"

# Extensions to standard DocTypes
# -------------------------------
# Registration only - every handler lives in our own overrides/ or quality/
# module. Enforcing through doc_events rather than form scripts means the rules
# also hold for /api/resource, /api/method and Data Import.
doc_events = {
	"Purchase Receipt": {
		"validate": "food_manufacturing.overrides.purchase_receipt.validate",
		"on_submit": "food_manufacturing.overrides.purchase_receipt.on_submit",
	},
	"Stock Entry": {
		"validate": "food_manufacturing.quality.batch_eligibility.validate_stock_entry",
		"on_submit": [
			"food_manufacturing.quality.batch_eligibility.validate_stock_entry",
			"food_manufacturing.production.yield_tracking.on_stock_entry_change",
		],
		"on_cancel": "food_manufacturing.production.yield_tracking.on_stock_entry_change",
	},
	"Delivery Note": {
		"validate": [
			"food_manufacturing.quality.batch_eligibility.validate_delivery_note",
			"food_manufacturing.dispatch.shelf_life.validate_delivery_note",
			"food_manufacturing.dispatch.fefo.validate_delivery_note",
		],
		"on_submit": [
			"food_manufacturing.quality.batch_eligibility.validate_delivery_note",
			"food_manufacturing.dispatch.shelf_life.validate_delivery_note",
		],
	},
	"Work Order": {
		"validate": "food_manufacturing.overrides.work_order.validate",
		"on_submit": "food_manufacturing.production.yield_tracking.on_work_order_submit",
	},
}

scheduler_events = {
	"daily": ["food_manufacturing.tasks.near_expiry.send_near_expiry_alerts"],
}

FM_MODULES = [
	"Food Manufacturing Setup",
	"Food Manufacturing Quality",
	"Food Manufacturing Recipe",
	"Food Manufacturing Production",
]

# Scoped fixtures - only records owned by this app's modules are exported.
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["module", "in", FM_MODULES]],
	},
	{
		"dt": "Property Setter",
		"filters": [["module", "in", FM_MODULES]],
	},
]

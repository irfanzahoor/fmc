app_name = "food_manufacturing"
# Batchwell is the product brand; the technical app and module names are
# unchanged, so existing installs, fixtures and imports keep working.
app_title = "Batchwell"
app_publisher = "Irfan Zahoor"
app_description = (
	"Spice and masala manufacturing on ERPNext: supplier lots, approved recipes, "
	"bulk blending, packaging and batch traceability"
)
app_email = "support@nextash.com"
app_license = "mit"
required_apps = ["frappe/erpnext"]

# Apps screen
# -----------
# The tile opens the Desk workspace, which is also the module's sidebar entry.
# `has_permission` keeps the icon off the screen of someone with no business in
# the plant, rather than showing a tile that refuses on click.
add_to_apps_screen = [
	{
		"name": app_name,
		"logo": "/assets/food_manufacturing/images/batchwell-logo.svg",
		"title": "Batchwell",
		"route": "/app/batchwell",
		"has_permission": "food_manufacturing.api.permission.has_app_permission",
	}
]

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

# Operator SPA
# ------------
# The Vue app is served at /fm; vue-router owns everything below that prefix.
website_route_rules = [
	{"from_route": "/fm/<path:app_path>", "to_route": "fm"},
]

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

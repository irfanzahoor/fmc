/**
 * The standard ERPNext roles each screen reads through.
 *
 * The console shows ERPNext's own documents, and the FM roles deliberately do
 * not widen access to them, so an operator needs both. These lists are the
 * narrowest role that grants read on what each screen's endpoint gates on
 * (`frappe.has_permission` calls in `food_manufacturing/api/`); they are shown
 * only when the server has already refused, to say what is missing.
 *
 * Kept in step with the role table in `docs/workflows.md`.
 */
export const SCREEN_ROLES = {
	// get_dashboard gates on Company, Work Order and Batch. Company is checked
	// as a document because the panels aggregate with get_all and db.count,
	// which do not apply User Permissions; Stock User is what grants it.
	overview: ['Item Manager', 'Manufacturing User', 'Stock User'],
	// get_production_queue and get_work_order_detail gate on Work Order.
	production: ['Manufacturing User'],
	// get_release_queue gates on Batch, Company and FM Batch Release; Company
	// is what an FM-only account is missing. get_batch_context also reads the
	// matching Quality Inspection, which on a stock site only ERPNext's own
	// Quality Manager grants - no FM role does.
	quality: ['Item Manager', 'Stock User', 'Quality Manager'],
	// get_open_purchase_orders gates on Purchase Order.
	receiving: ['Purchase User'],
	// get_open_sales_orders gates on Sales Order.
	dispatch: ['Sales User'],
	// get_recall gates on Company, Batch, Delivery Note and Stock Ledger Entry.
	recall: ['Item Manager', 'Stock User'],
	// simulate_recipe_cost gates on BOM; the packaging planner reads Item and Bin.
	// get_costable_boms also checks Company as a document, because it reads with
	// get_all on purpose: the rule that hides a recipe's BOM from list queries
	// would otherwise empty the very screen that is meant to give the totals.
	costing: ['Item Manager', 'Manufacturing User', 'Stock User'],
}

/**
 * Mock of @/data/api for the design harness.
 *
 * Aliased in place of the real module by vite.preview.config.js, so the harness
 * mounts the *real* pages, router and shell and only the network layer is
 * replaced. Shapes mirror food_manufacturing/api/ exactly; if a page renders
 * here it renders against the real endpoint.
 */
/*
 * `?deny` makes every read fail the way the server does when the account is
 * missing one of the standard ERPNext roles, so that state can be looked at
 * rather than reasoned about.
 */
const DENIED = typeof location !== 'undefined' && new URLSearchParams(location.search).has('deny')

const refuse = () =>
	Promise.reject(
		Object.assign(new Error('Insufficient Permission'), {
			exc_type: 'PermissionError',
			status: 403,
			messages: [
				'User <strong>operator@fmc.local</strong> does not have doctype access via role permission for document <strong>Work Order</strong>',
			],
		}),
	)

const delay = (value) =>
	DENIED ? refuse() : new Promise((resolve) => setTimeout(() => resolve(value), 0))

const KG = 'Kg'
const NOS = 'Nos'

// Mirrors api/dashboards.py: panels of metrics, each linking to its source.
export const roleDashboard = {
	views: () => delay(['owner', 'production', 'quality', 'stores']),
	get: ({ view = 'owner' } = {}) =>
		delay({
			company: 'FM Demo Foods',
			currency: 'PKR',
			view,
			period_days: 30,
			since: '2026-09-23',
			available: ['owner', 'production', 'quality', 'stores'],
			panels: {
				owner: [
					{
						title: 'Needs a decision',
						note: null,
						kind: 'material_short',
						total: 3,
						rows: [
							{
								work_order: 'MFG-WO-2026-00041', item_name: 'Garam Masala Bulk',
								status: 'Not Started', planned_end_date: '2026-10-28',
								items: [
									{ item_code: 'CHI', item_name: 'Red Chilli Powder', warehouse: 'FM Demo Stores - SED',
									  required_qty: 300, available_qty: 54, short_qty: 246, uom: 'Kg' },
									{ item_code: 'CUM', item_name: 'Cumin Powder', warehouse: 'FM Demo Stores - SED',
									  required_qty: 200, available_qty: 56, short_qty: 144, uom: 'Kg' },
								],
							},
						],
						metrics: [
							{ label: 'Runs short of material', value: 3, unit: '', decimals: 0, tone: 'warn', link: { doctype: 'Work Order', filters: {} } },
							{ label: 'Batches held or quarantined', value: 5, unit: '', decimals: 0, tone: 'warn', link: { doctype: 'Batch', filters: {} } },
							{ label: 'Runs past their end date', value: 1, unit: '', decimals: 0, tone: 'warn', link: { doctype: 'Work Order', filters: {} } },
						],
					},
					{
						title: 'Production',
						note: null,
						rows: [],
						metrics: [
							{ label: 'Completed runs', value: 18, unit: '', decimals: 0, tone: 'neutral', link: { doctype: 'Work Order', filters: { status: 'Completed' } } },
							{ label: 'Open runs', value: 4, unit: '', decimals: 0, tone: 'neutral', link: { doctype: 'Work Order', filters: { status: 'In Process' } } },
							{ label: 'Average actual yield', value: 96.4, unit: '%', decimals: 1, tone: 'neutral', link: null },
							{ label: 'Runs outside tolerance', value: 2, unit: '', decimals: 0, tone: 'warn', link: { doctype: 'Work Order', filters: { fm_yield_flagged: 1 } } },
						],
					},
					{
						title: 'Cost variance',
						note: '14 of 18 runs could be costed. A run whose BOM carries no cost has no estimate to compare against.',
						rows: [],
						metrics: [
							{ label: 'Estimated cost', value: 142000, unit: '', decimals: 0, tone: 'neutral', currency: true, link: null },
							{ label: 'Actual cost', value: 148600, unit: '', decimals: 0, tone: 'neutral', currency: true, link: { doctype: 'Stock Entry', filters: { purpose: 'Manufacture' } } },
							{ label: 'Variance', value: 6600, unit: '', decimals: 0, tone: 'warn', currency: true, link: null },
							{ label: 'Runs over plan', value: 5, unit: '', decimals: 0, tone: 'warn', link: null },
						],
					},
					{
						title: 'Stock and quality',
						note: null,
						rows: [],
						metrics: [
							{ label: 'Batches awaiting a decision', value: 5, unit: '', decimals: 0, tone: 'warn', link: { doctype: 'Batch', filters: { fm_quality_status: 'Quarantine' } } },
							{ label: 'Near expiry', value: 11, unit: '', decimals: 0, tone: 'warn', link: { doctype: 'Batch', filters: {} } },
							{ label: 'Released in period', value: 23, unit: '', decimals: 0, tone: 'good', link: { doctype: 'FM Batch Release', filters: { decision: 'Release' } } },
						],
					},
				],
				production: [
					{
						title: 'Work queue',
						note: null,
						rows: [],
						metrics: [
							{ label: 'Open runs', value: 4, unit: '', decimals: 0, tone: 'neutral', link: { doctype: 'Work Order', filters: {} } },
							{ label: 'Ready to start', value: 3, unit: '', decimals: 0, tone: 'neutral', link: null },
							{ label: 'Completed in period', value: 18, unit: '', decimals: 0, tone: 'good', link: null },
						],
					},
					{
						title: 'Output',
						note: null,
						rows: [],
						metrics: [
							{ label: 'Average actual yield', value: 96.4, unit: '%', decimals: 1, tone: 'neutral', link: null },
							{ label: 'Runs outside tolerance', value: 2, unit: '', decimals: 0, tone: 'warn', link: { doctype: 'Work Order', filters: {} } },
						],
					},
				],
				quality: [
					{
						title: 'Decisions waiting',
						note: null,
						rows: [],
						metrics: [
							{ label: 'In quarantine', value: 8, unit: '', decimals: 0, tone: 'warn', link: { doctype: 'Batch', filters: {} } },
							{ label: 'On hold', value: 4, unit: '', decimals: 0, tone: 'warn', link: { doctype: 'Batch', filters: {} } },
							{ label: 'Total awaiting', value: 12, unit: '', decimals: 0, tone: 'warn', link: null },
						],
					},
					{
						title: 'Inspections',
						note: null,
						rows: [],
						metrics: [
							{ label: 'Draft inspections', value: 3, unit: '', decimals: 0, tone: 'neutral', link: { doctype: 'Quality Inspection', filters: { docstatus: 0 } } },
							{ label: 'Decisions recorded in period', value: 23, unit: '', decimals: 0, tone: 'good', link: { doctype: 'FM Batch Release', filters: {} } },
						],
					},
				],
				stores: [
					{
						title: 'Goods in',
						note: null,
						rows: [],
						metrics: [
							{ label: 'Open purchase orders', value: 6, unit: '', decimals: 0, tone: 'neutral', link: { doctype: 'Purchase Order', filters: {} } },
							{ label: 'Received in period', value: 14, unit: '', decimals: 0, tone: 'good', link: { doctype: 'Purchase Receipt', filters: {} } },
						],
					},
					{
						title: 'Shortages',
						note: 'Plan a packing run to see what it is short of.',
						rows: [],
						metrics: [
							{ label: 'Open material requests', value: 2, unit: '', decimals: 0, tone: 'warn', link: { doctype: 'Material Request', filters: {} } },
						],
					},
					{
						title: 'Near expiry',
						note: null,
						rows: [],
						metrics: [
							{ label: 'Batches within 90 days', value: 11, unit: '', decimals: 0, tone: 'warn', link: { doctype: 'Batch', filters: {} } },
						],
					},
				],
			}[view],
		}),
}

export const costing = {
	boms: () => delay([
		{ name: 'BOM-GM-BULK-001', item: 'GM-BULK', item_name: 'Garam Masala Bulk',
		  quantity: 100, uom: KG, currency: 'PKR', rm_cost_as_per: 'Valuation Rate' },
	]),
	packsFor: () => delay([
		{ item_code: 'GM-50G', item_name: 'Garam Masala 50 g', fm_pack_size: 0.05, fm_pack_uom: KG },
		{ item_code: 'GM-100G', item_name: 'Garam Masala 100 g', fm_pack_size: 0.1, fm_pack_uom: KG },
	]),
	simulate: () => delay({
		basis: 'estimate', bom: 'BOM-GM-BULK-001', item: 'GM-BULK',
		company: 'FM Demo Foods', currency: 'PKR', shows_ingredient_detail: true,
		scenario: null, delta: null,
		baseline: {
			batch_qty: 100, batch_uom: KG, yield_percent: 97, good_qty: 97,
			ingredient_cost: 8000, packaging_cost: 0, operating_cost: 1200, total_cost: 9200,
			cost_per_unit: 94.85,
			ingredients: [
				{ item_code: 'CHI', item_name: 'Red Chilli Powder', qty: 60, uom: KG,
				  bom_qty: 60, bom_uom: KG, conversion_factor: 1, rate: 100, amount: 6000,
				  rate_source: 'Moving-average valuation, as costed on this BOM', overridden: false },
				{ item_code: 'CUM', item_name: 'Cumin Powder', qty: 40, uom: KG,
				  bom_qty: 40, bom_uom: KG, conversion_factor: 1, rate: 50, amount: 2000,
				  rate_source: 'Moving-average valuation, as costed on this BOM', overridden: false },
			],
			packaging: [],
			packs: [
				{ item_code: 'GM-50G', item_name: 'Garam Masala 50 g', pack_size: 0.05,
				  pack_uom: KG, bulk_item: 'GM-BULK', packs_per_batch: 1940,
				  cost_per_pack: 4.74, requested_qty: null, note: null },
			],
			assumptions: [
				'Estimated cost, not ledger valuation. Actual batch cost comes from submitted stock transactions.',
				'Material priced as Valuation Rate, the source this BOM declares.',
				'Cost is spread over good output at 97% yield.',
			],
		},
	}),
	planPackaging: () => delay({
		company: 'FM Demo Foods', loss_percent: 2, has_shortage: true,
		notes: [],
		lines: [
			{ item_code: 'GM-BULK', item_name: 'Garam Masala Bulk', uom: KG, role: '1-blend',
			  required_qty: 51, conversion: { from_qty: 50, from_uom: 'Gram', factor: 0.001, to_uom: KG },
			  actual_qty: 201, committed_qty: 0, requested_qty: 0, expected_qty: 0,
			  available_qty: 201, shortage_qty: 0, sources: [] },
			{ item_code: 'POUCH-50', item_name: 'Pouch 50 g', uom: NOS, role: '2-packaging',
			  required_qty: 1020, conversion: null,
			  actual_qty: 400, committed_qty: 0, requested_qty: 0, expected_qty: 200,
			  available_qty: 400, shortage_qty: 420, sources: [] },
			{ item_code: 'LABEL-50', item_name: 'Label 50 g', uom: NOS, role: '2-packaging',
			  required_qty: 1020, conversion: null,
			  actual_qty: 1500, committed_qty: 0, requested_qty: 0, expected_qty: 0,
			  available_qty: 1500, shortage_qty: 0, sources: [] },
		],
	}),
	requestShortfall: () => delay({ material_request: 'MAT-MR-2026-00012', created: true, shortages: [] }),
}

export const dashboard = {
	get: () =>
		delay({
			company: 'FM Demo Foods',
			period_days: 30,
			kpis: {
				average_yield_percent: 96.4,
				completed_runs: 18,
				open_runs: 4,
				yield_flagged: 2,
				pending_qc: 5,
				near_expiry: 11,
				batches_released: 23,
			},
			yield_trend: [
				{ label: 'WO-0031', item: 'Garam Masala Bulk', actual: 97.0, planned: 100, flagged: 0, on: '2026-09-24' },
				{ label: 'WO-0032', item: 'Chaat Masala Bulk', actual: 96.2, planned: 100, flagged: 0, on: '2026-09-26' },
				{ label: 'WO-0033', item: 'Garam Masala Bulk', actual: 97.4, planned: 100, flagged: 0, on: '2026-09-29' },
				{ label: 'WO-0034', item: 'Tandoori Masala Bulk', actual: 92.1, planned: 100, flagged: 1, on: '2026-10-02' },
				{ label: 'WO-0035', item: 'Garam Masala Bulk', actual: 96.8, planned: 100, flagged: 0, on: '2026-10-05' },
				{ label: 'WO-0036', item: 'Chilli Powder Bulk', actual: 98.1, planned: 100, flagged: 0, on: '2026-10-08' },
				{ label: 'WO-0037', item: 'Chaat Masala Bulk', actual: 95.9, planned: 100, flagged: 0, on: '2026-10-11' },
				{ label: 'WO-0038', item: 'Garam Masala Bulk', actual: 97.2, planned: 100, flagged: 0, on: '2026-10-14' },
				{ label: 'WO-0039', item: 'Turmeric Bulk', actual: 93.4, planned: 100, flagged: 1, on: '2026-10-17' },
				{ label: 'WO-0040', item: 'Garam Masala Bulk', actual: 97.6, planned: 100, flagged: 0, on: '2026-10-19' },
				{ label: 'WO-0041', item: 'Chilli Powder Bulk', actual: 98.4, planned: 100, flagged: 0, on: '2026-10-21' },
				{ label: 'WO-0042', item: 'Garam Masala Bulk', actual: 97.1, planned: 100, flagged: 0, on: '2026-10-22' },
			],
			production_by_item: [
				{ item_code: 'GM-BULK', label: 'Garam Masala Bulk', uom: KG, nature: 'Bulk Blend', value: 1842.5, loss: 56.2, runs: 6 },
				{ item_code: 'CM-BULK', label: 'Chaat Masala Bulk', uom: KG, nature: 'Bulk Blend', value: 1120, loss: 44.8, runs: 4 },
				{ item_code: 'CP-BULK', label: 'Chilli Powder Bulk', uom: KG, nature: 'Bulk Blend', value: 960, loss: 18, runs: 3 },
				{ item_code: 'GM-50G', label: 'Garam Masala 50 g', uom: NOS, nature: 'Finished Good', value: 24000, loss: 0, runs: 3 },
				{ item_code: 'TM-BULK', label: 'Tandoori Masala Bulk', uom: KG, nature: 'Bulk Blend', value: 420, loss: 34, runs: 1 },
			],
			quality_mix: [
				{ label: 'Released', role: 'good', value: 48 },
				{ label: 'Quarantine', role: 'warning', value: 8 },
				{ label: 'Rejected', role: 'critical', value: 3 },
				{ label: 'Hold', role: 'serious', value: 4 },
			],
			yield_exceptions: [
				{ work_order: 'MFG-WO-2026-00034', item_code: 'TM-BULK', item_name: 'Tandoori Masala Bulk', uom: 'Kg',
				  input_qty: 500, produced_qty: 457, loss_qty: 43, yield_percent: 91.4, planned_percent: 100,
				  basis: 'Input vs output', on: '2026-10-08' },
				{ work_order: 'MFG-WO-2026-00039', item_code: 'TU-BULK', item_name: 'Turmeric Bulk', uom: 'Kg',
				  input_qty: 400, produced_qty: 354, loss_qty: 46, yield_percent: 88.5, planned_percent: 100,
				  basis: 'Input vs output', on: '2026-10-16' },
			],
			expiry_buckets: [
				{ label: 'Expired', value: 1 },
				{ label: 'Within 7 days', value: 3 },
				{ label: '8-30 days', value: 5 },
				{ label: '31-90 days', value: 14 },
			],
		}),
}

const WORK_ORDERS = [
	{
		name: 'WO-FM-0028', production_item: 'GM-BULK', item_name: 'Garam Masala Bulk', bom_no: 'BOM-GM-004',
		qty: 500, produced_qty: 0, process_loss_qty: 0, status: 'In Process', short_items: 0, material_ready: true, stock_uom: KG,
		fg_warehouse: 'Bulk Blend', wip_warehouse: 'Stores', planned_start_date: '2026-10-23',
		fm_actual_yield_percent: 0, fm_yield_variance_percent: 0, fm_yield_flagged: 0, fm_yield_basis: KG,
		pending_qty: 500,
	},
	{
		name: 'WO-FM-0029', production_item: 'GM-50G', item_name: 'Garam Masala 50 g', bom_no: 'BOM-GM50-002',
		qty: 2400, produced_qty: 0, process_loss_qty: 0, status: 'Not Started', short_items: 0, material_ready: true, stock_uom: NOS,
		fg_warehouse: 'Finished Goods', wip_warehouse: 'Stores', planned_start_date: '2026-10-23',
		fm_actual_yield_percent: 0, fm_yield_variance_percent: 0, fm_yield_flagged: 0, fm_yield_basis: '',
		pending_qty: 2400,
	},
	{
		name: 'WO-FM-0030', production_item: 'TU-BULK', item_name: 'Turmeric Powder Bulk', bom_no: 'BOM-TU-001',
		qty: 400, produced_qty: 100, process_loss_qty: 6, status: 'In Process', short_items: 0, material_ready: true, stock_uom: KG,
		fg_warehouse: 'Bulk Blend', wip_warehouse: 'Stores', planned_start_date: '2026-10-22',
		fm_actual_yield_percent: 93.4, fm_yield_variance_percent: -6.6, fm_yield_flagged: 1, fm_yield_basis: KG,
		pending_qty: 294,
	},
]

// Mirrors mockSession: four companies, one of them actually set up.
export const bootstrap = {
	get: () => delay({
		companies: ['Steps ERP', 'Steps ERP (Demo)', 'Steps Real Estate (Qatar)', 'Steps Real Estate Group'],
		configured: ['Steps ERP (Demo)'],
		default: 'Steps ERP (Demo)',
		user: 'demo@fmc.local',
	}),
}

export const production = {
	queue: () => delay(WORK_ORDERS),
	detail: ({ work_order }) => {
		const wo = WORK_ORDERS.find((row) => row.name === work_order) || WORK_ORDERS[0]
		return delay({
			material_ready: true,
			next_action: { action: 'complete', label: 'Complete run', enabled: true, reason: null },
			work_order: {
				name: wo.name, production_item: wo.production_item, item_name: wo.item_name,
				bom_no: wo.bom_no, qty: wo.qty, produced_qty: wo.produced_qty,
				process_loss_qty: wo.process_loss_qty, status: wo.status, stock_uom: wo.stock_uom,
				company: 'FM Demo Foods', fg_warehouse: wo.fg_warehouse, wip_warehouse: wo.wip_warehouse,
				skip_transfer: 1, yield_percent: wo.fm_actual_yield_percent,
				yield_variance_percent: wo.fm_yield_variance_percent,
				yield_flagged: wo.fm_yield_flagged, yield_basis: wo.fm_yield_basis,
			},
			ingredients: [
				{
					item_code: 'CHI', item_name: 'Chilli Powder', required_qty: 300, transferred_qty: 0,
					consumed_qty: 0, stock_uom: KG, source_warehouse: 'Stores',
					available_lots: [
						{ batch_no: 'CHI-014', available_qty: 450, expiry_date: '2027-01-12', manufacturing_date: '2026-01-12', quality_status: 'Released' },
						{ batch_no: 'CHI-018', available_qty: 120, expiry_date: '2027-03-02', manufacturing_date: '2026-03-02', quality_status: 'Released' },
					],
				},
				{
					item_code: 'CUM', item_name: 'Cumin Whole', required_qty: 125, transferred_qty: 0,
					consumed_qty: 0, stock_uom: KG, source_warehouse: 'Stores',
					available_lots: [
						{ batch_no: 'CUM-009', available_qty: 180, expiry_date: '2027-02-20', manufacturing_date: '2026-02-20', quality_status: 'Released' },
					],
				},
				{
					item_code: 'COR', item_name: 'Coriander', required_qty: 50, transferred_qty: 0,
					consumed_qty: 0, stock_uom: KG, source_warehouse: 'Stores', available_lots: [],
				},
				{
					item_code: 'PEP', item_name: 'Black Pepper', required_qty: 25, transferred_qty: 0,
					consumed_qty: 0, stock_uom: KG, source_warehouse: 'Stores',
					available_lots: [
						{ batch_no: 'PEP-006', available_qty: 40, expiry_date: '2027-04-15', manufacturing_date: '2026-04-15', quality_status: 'Released' },
					],
				},
			],
			consumed_lots: [],
		})
	},
	finishRun: () => delay({ stock_entry: 'MAT-STE-2026-00142', produced_qty: 487, process_loss_qty: 13, yield_percent: 97.4, yield_flagged: 0, yield_basis: KG }),
}

const QUEUE = [
	{ name: 'CHI-014', item: 'CHI', item_name: 'Chilli Powder', fm_quality_status: 'Quarantine', fm_supplier_lot_no: 'SV-261001', supplier: 'Spice Valley', expiry_date: '2027-01-12', manufacturing_date: '2026-01-12', creation: '2026-10-18 09:15:00', qty: 450, stock_uom: KG, remaining_shelf_life_percent: 62 },
	{ name: 'CUM-009', item: 'CUM', item_name: 'Cumin Whole', fm_quality_status: 'Quarantine', fm_supplier_lot_no: 'RJ-99420', supplier: 'Rajasthan Spice Co', expiry_date: '2027-02-20', manufacturing_date: '2026-02-20', creation: '2026-10-19 11:02:00', qty: 180, stock_uom: KG, remaining_shelf_life_percent: 71 },
	{ name: 'COR-021', item: 'COR', item_name: 'Coriander', fm_quality_status: 'Hold', fm_supplier_lot_no: 'GUJ-1102', supplier: 'Gujarat Agro', expiry_date: '2027-03-11', manufacturing_date: '2026-03-11', creation: '2026-10-20 08:40:00', qty: 90, stock_uom: KG, remaining_shelf_life_percent: 58 },
	{ name: 'PEP-006', item: 'PEP', item_name: 'Black Pepper', fm_quality_status: 'Quarantine', fm_supplier_lot_no: 'KL-8831', supplier: 'Kerala Estates', expiry_date: '2027-04-15', manufacturing_date: '2026-04-15', creation: '2026-10-21 14:25:00', qty: 40, stock_uom: KG, remaining_shelf_life_percent: 80 },
	{ name: 'TUR-015', item: 'TUR', item_name: 'Turmeric Whole', fm_quality_status: 'Quarantine', fm_supplier_lot_no: 'TN-4029', supplier: 'Tamil Nadu Farms', expiry_date: '2026-12-02', manufacturing_date: '2026-02-02', creation: '2026-10-22 07:10:00', qty: 320, stock_uom: KG, remaining_shelf_life_percent: 18 },
]

export const quality = {
	queue: () => delay(QUEUE),
	counts: () => delay({ quarantine: 4, hold: 1, total: 5 }),
	batchContext: ({ batch }) => {
		const row = QUEUE.find((b) => b.name === batch) || QUEUE[0]
		return delay({
			batch: {
				name: row.name, item: row.item, item_name: row.item_name,
				quality_status: row.fm_quality_status, supplier_lot_no: row.fm_supplier_lot_no,
				supplier: row.supplier, expiry_date: row.expiry_date,
				manufacturing_date: row.manufacturing_date,
				remaining_shelf_life_percent: row.remaining_shelf_life_percent,
				qty: row.qty, stock_uom: KG,
			},
			inspections: [
				{ name: 'QI-0021', status: 'Accepted', inspection_type: 'Incoming', report_date: '2026-10-22' },
				{ name: 'QI-0019', status: 'Accepted', inspection_type: 'Incoming', report_date: '2026-10-18' },
			],
			history: [
				{ name: 'FM-REL-0004', decision: 'Hold', reason: 'Awaiting lab moisture result', decided_by: 'quality@demo', posting_datetime: '2026-10-22 11:30:00', previous_status: 'Quarantine' },
			],
			genealogy: { item_code: row.item, batch_no: row.name, work_orders: [], inputs: [], truncated: false },
		})
	},
	recordDecision: ({ batch, decision }) => delay({ name: 'FM-REL-0012', batch, previous_status: 'Quarantine', quality_status: decision === 'Release' ? 'Released' : decision === 'Hold' ? 'Hold' : 'Rejected' }),
}

export const receiving = {
	openOrders: () => delay([
		{ name: 'PO-FM-0044', supplier: 'SPICE-VALLEY', supplier_name: 'Spice Valley', transaction_date: '2026-10-20', per_received: 0, currency: 'INR' },
		{ name: 'PO-FM-0045', supplier: 'KERALA-EST', supplier_name: 'Kerala Estates', transaction_date: '2026-10-21', per_received: 40, currency: 'INR' },
	]),
	orderLines: ({ purchase_order }) => delay({
		purchase_order, supplier: 'SPICE-VALLEY', supplier_name: 'Spice Valley', company: 'FM Demo Foods',
		quarantine_warehouse: 'FM Quarantine', requires_inspection: true,
		lines: [
			{ idx: 1, name: 'poi-1', item_code: 'CHI', item_name: 'Chilli Powder', uom: KG, stock_uom: KG, rate: 300, ordered_qty: 500, received_qty: 0, pending_qty: 500, material_nature: 'Raw Material', has_batch_no: 1, needs_inspection: true, warehouse: 'Stores' },
			{ idx: 2, name: 'poi-2', item_code: 'CUM', item_name: 'Cumin Whole', uom: KG, stock_uom: KG, rate: 420, ordered_qty: 250, received_qty: 0, pending_qty: 250, material_nature: 'Raw Material', has_batch_no: 1, needs_inspection: true, warehouse: 'Stores' },
			{ idx: 3, name: 'poi-3', item_code: 'POUCH50', item_name: 'Pouch 50 g', uom: NOS, stock_uom: NOS, rate: 2, ordered_qty: 5000, received_qty: 0, pending_qty: 5000, material_nature: 'Packaging Material', has_batch_no: 0, needs_inspection: true, warehouse: 'Stores' },
		],
	}),
	receive: () => delay({ purchase_receipt: 'MAT-PRE-2026-00031', warehouses: ['FM Quarantine'], batches: [{ name: 'CHI-021', item: 'CHI', fm_quality_status: 'Quarantine', fm_supplier_lot_no: 'SV-261044', expiry_date: '2028-02-01' }] }),
}

export const dispatch = {
	openOrders: () => delay([
		{ name: 'SO-FM-0036', customer: 'APEX', customer_name: 'Apex Retailers', transaction_date: '2026-10-18', delivery_date: '2026-10-25', per_delivered: 0 },
		{ name: 'SO-FM-0037', customer: 'METRO', customer_name: 'Metro Wholesale', transaction_date: '2026-10-19', delivery_date: '2026-10-28', per_delivered: 25 },
	]),
	picklist: ({ sales_order }) => delay({
		sales_order, customer: 'APEX', customer_name: 'Apex Retailers', company: 'FM Demo Foods',
		fefo_mode: 'Block', min_remaining_shelf_life_percent: 30,
		lines: [
			{
				name: 'soi-1', idx: 1, item_code: 'GM-50G', item_name: 'Garam Masala 50 g', uom: 'Carton', stock_uom: NOS, nature: 'Finished Good',
				rate: 1440, ordered_qty: 2, delivered_qty: 0, pending_qty: 48, warehouse: 'Finished Goods',
				suggestion: [{ batch_no: 'GM50-021', qty: 48 }], shortfall: 0,
				candidates: [
					{ batch_no: 'GM50-021', available_qty: 72, expiry_date: '2027-02-14', manufacturing_date: '2026-02-14', quality_status: 'Released', remaining_shelf_life_percent: 62, blocked_reason: null },
					{ batch_no: 'GM50-008', available_qty: 50, expiry_date: '2027-01-18', manufacturing_date: '2026-01-18', quality_status: 'Hold', remaining_shelf_life_percent: 58, blocked_reason: 'Held stock cannot be dispatched.' },
				],
			},
			{
				name: 'soi-2', idx: 2, item_code: 'GM-100G', item_name: 'Garam Masala 100 g', uom: 'Carton', stock_uom: NOS, nature: 'Finished Good',
				rate: 2640, ordered_qty: 1, delivered_qty: 0, pending_qty: 24, warehouse: 'Finished Goods',
				suggestion: [{ batch_no: 'GM100-009', qty: 24 }], shortfall: 0,
				candidates: [
					{ batch_no: 'GM100-009', available_qty: 36, expiry_date: '2027-02-20', manufacturing_date: '2026-02-20', quality_status: 'Released', remaining_shelf_life_percent: 65, blocked_reason: null },
				],
			},
		],
	}),
	createDeliveryNote: () => delay({ delivery_note: 'MAT-DN-2026-00048' }),
}

export const recall = {
	get: () => delay({
		truncated: false,
		batches: [
			{ name: 'CHI-014', item: 'Chilli Powder', fm_supplier_lot_no: 'SV-261001', fm_quality_status: 'Released' },
			{ name: 'GM-BULK-031', item: 'Garam Masala Bulk', fm_supplier_lot_no: null, fm_quality_status: 'Released' },
			{ name: 'GM50-021', item: 'Garam Masala 50 g', fm_supplier_lot_no: null, fm_quality_status: 'Released' },
			{ name: 'GM100-009', item: 'Garam Masala 100 g', fm_supplier_lot_no: null, fm_quality_status: 'Hold' },
		],
		deliveries: [
			{ delivery_note: 'MAT-DN-2026-00041', customer: 'Apex Retailers', batch_no: 'GM50-021', item_code: 'GM-50G', posting_date: '2026-10-14', stock_qty: 480, stock_uom: NOS, nature: 'Finished Good', is_return: 0 },
			{ delivery_note: 'MAT-DN-2026-00044', customer: 'Metro Wholesale', batch_no: 'GM100-009', item_code: 'GM-100G', posting_date: '2026-10-17', stock_qty: 240, stock_uom: NOS, nature: 'Finished Good', is_return: 0 },
			{ delivery_note: 'MAT-DN-2026-00046', customer: 'Apex Retailers', batch_no: 'GM50-021', item_code: 'GM-50G', posting_date: '2026-10-20', stock_qty: -24, stock_uom: NOS, nature: 'Finished Good', is_return: 1 },
		],
	}),
}

export function errorMessage(error) {
	if (!error) return null
	const messages = error.messages
	if (Array.isArray(messages) && messages.length) {
		return messages.map((m) => String(m).replace(/<[^>]*>/g, '')).join('\n')
	}
	return error.message || String(error)
}

export function isPermissionError(error) {
	return error?.exc_type === 'PermissionError' || error?.status === 403
}

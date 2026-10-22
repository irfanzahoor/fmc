/**
 * Representative data for the design harness.
 *
 * Shaped exactly like food_manufacturing.api.dashboard.get_dashboard returns,
 * so the harness exercises the real components against a realistic payload.
 * Numbers follow the acceptance scenario: a 100 kg blend yielding 97 kg.
 */
export const dashboard = {
	company: 'Shahi Masala Works',
	period_days: 30,
	kpis: {
		average_yield_percent: 96.4,
		completed_runs: 18,
		open_runs: 4,
		yield_flagged: 2,
		pending_qc: 6,
		near_expiry: 11,
		batches_released: 23,
	},
	yield_trend: [
		{ label: 'MFG-WO-0031', item: 'Garam Masala Bulk', actual: 97.0, planned: 100, flagged: 0, on: '2026-09-24' },
		{ label: 'MFG-WO-0032', item: 'Chaat Masala Bulk', actual: 96.2, planned: 100, flagged: 0, on: '2026-09-26' },
		{ label: 'MFG-WO-0033', item: 'Garam Masala Bulk', actual: 97.4, planned: 100, flagged: 0, on: '2026-09-29' },
		{ label: 'MFG-WO-0034', item: 'Tandoori Masala Bulk', actual: 92.1, planned: 100, flagged: 1, on: '2026-10-02' },
		{ label: 'MFG-WO-0035', item: 'Garam Masala Bulk', actual: 96.8, planned: 100, flagged: 0, on: '2026-10-05' },
		{ label: 'MFG-WO-0036', item: 'Chilli Powder Bulk', actual: 98.1, planned: 100, flagged: 0, on: '2026-10-08' },
		{ label: 'MFG-WO-0037', item: 'Chaat Masala Bulk', actual: 95.9, planned: 100, flagged: 0, on: '2026-10-11' },
		{ label: 'MFG-WO-0038', item: 'Garam Masala Bulk', actual: 97.2, planned: 100, flagged: 0, on: '2026-10-14' },
		{ label: 'MFG-WO-0039', item: 'Turmeric Bulk', actual: 93.4, planned: 100, flagged: 1, on: '2026-10-17' },
		{ label: 'MFG-WO-0040', item: 'Garam Masala Bulk', actual: 97.6, planned: 100, flagged: 0, on: '2026-10-19' },
		{ label: 'MFG-WO-0041', item: 'Chilli Powder Bulk', actual: 98.4, planned: 100, flagged: 0, on: '2026-10-21' },
		{ label: 'MFG-WO-0042', item: 'Garam Masala Bulk', actual: 97.1, planned: 100, flagged: 0, on: '2026-10-22' },
	],
	production_by_item: [
		{ item_code: 'GM-BULK', label: 'Garam Masala Bulk', uom: 'Kg', value: 1842.5, loss: 56.2, runs: 6 },
		{ item_code: 'CM-BULK', label: 'Chaat Masala Bulk', uom: 'Kg', value: 1120.0, loss: 44.8, runs: 4 },
		{ item_code: 'CP-BULK', label: 'Chilli Powder Bulk', uom: 'Kg', value: 960.0, loss: 18.0, runs: 3 },
		{ item_code: 'GM-50G', label: 'Garam Masala 50 g', uom: 'Nos', value: 24000, loss: 0, runs: 3 },
		{ item_code: 'TM-BULK', label: 'Tandoori Masala Bulk', uom: 'Kg', value: 420.0, loss: 34.0, runs: 1 },
		{ item_code: 'TU-BULK', label: 'Turmeric Bulk', uom: 'Kg', value: 310.0, loss: 21.0, runs: 1 },
	],
	quality_mix: [
		{ label: 'Released', role: 'good', value: 48 },
		{ label: 'Quarantine', role: 'warning', value: 6 },
		{ label: 'Rejected', role: 'critical', value: 3 },
		{ label: 'Hold', role: 'serious', value: 2 },
	],
	expiry_buckets: [
		{ label: 'Expired', value: 1 },
		{ label: 'Within 7 days', value: 1 },
		{ label: '8-30 days', value: 3 },
		{ label: '31-90 days', value: 7 },
	],
}

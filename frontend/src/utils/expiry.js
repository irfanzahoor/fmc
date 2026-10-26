/**
 * The expiry scale, and the ramp step each bucket owns.
 *
 * Kept in step with `EXPIRY_BUCKETS` in `food_manufacturing/api/dashboard.py`.
 * Both dashboards read it, and they had grown a copy each.
 *
 * Two rules live here:
 *
 * 1. **The ramp step follows the bucket, never its position in today's rows.**
 *    `_expiry_buckets` leaves out a bucket holding nothing, so stepping the ramp
 *    by index repaints the survivors: "Within 7 days" would wear the darkest
 *    step on a day with no expired stock and the second step on a day with some.
 *
 * 2. **A bucket the response left out is a zero, not a gap.** The server starts
 *    every bucket at 0 and then filters `if counts[label]`, so the omission is a
 *    measured zero. A time scale with a step missing from the middle reads as if
 *    the question was never asked; "Expired — 0" answers it, and it also stops
 *    the chart changing width with the day's data.
 *
 * An entirely empty list still means "nothing to show": with no warehouse in the
 * company the server returns `[]` before it counts anything.
 */
export const EXPIRY_SCALE = [
	{ label: 'Expired', color: 'var(--viz-ordinal-4)' },
	{ label: 'Within 7 days', color: 'var(--viz-ordinal-3)' },
	{ label: '8-30 days', color: 'var(--viz-ordinal-2)' },
	{ label: '31-90 days', color: 'var(--viz-ordinal-1)' },
]

export function toExpiryRows(buckets) {
	const rows = buckets || []
	if (!rows.length) return []

	const counted = new Map(rows.map((row) => [row.label, Number(row.value) || 0]))
	const known = new Set(EXPIRY_SCALE.map((step) => step.label))

	return [
		...EXPIRY_SCALE.map((step) => ({
			label: step.label,
			value: counted.get(step.label) ?? 0,
			color: step.color,
		})),
		// A label this scale does not know about is still shown, uncoloured and
		// in the order the server sent it, rather than silently dropped.
		...rows.filter((row) => !known.has(row.label)).map((row) => ({
			label: row.label,
			value: Number(row.value) || 0,
		})),
	]
}

/**
 * A tick scale on round numbers.
 *
 * The previous axis padded the data by a fixed amount and snapped to multiples
 * of five. With yields clustered between 92% and 97% and a 100% planned line in
 * the domain, that produced an 85-105 band: the data occupied a quarter of the
 * plot and every run looked identical. The step is chosen from the data's own
 * range instead, so the variation that matters is the variation you see.
 */
const STEPS = [1, 2, 2.5, 5]

/**
 * @param {number} min    smallest value to show
 * @param {number} max    largest value to show
 * @param {object} [opts]
 * @param {number} [opts.ticks=5]   how many gridlines to aim for
 * @param {number} [opts.floor]     a value the domain may never go below
 * @param {number} [opts.ceiling]   a value the domain may never go above
 * @returns {{min: number, max: number, ticks: number[]}}
 */
export function niceScale(min, max, opts = {}) {
	const { ticks = 5, floor = null, ceiling = null } = opts

	if (!Number.isFinite(min) || !Number.isFinite(max)) {
		return { min: 0, max: 1, ticks: [0, 1] }
	}

	let lo = Math.min(min, max)
	let hi = Math.max(min, max)

	// A flat series still needs a band to sit in, or every point lands on one line.
	if (hi - lo < 1e-9) {
		const nudge = Math.max(Math.abs(hi) * 0.05, 1)
		lo -= nudge
		hi += nudge
	}

	// Breathing room, proportional to the data rather than a fixed constant -
	// and never past a hard edge, so padding cannot reintroduce the empty band.
	const pad = (hi - lo) * 0.12
	lo -= pad
	hi += pad
	if (floor !== null) lo = Math.max(lo, floor)
	if (ceiling !== null) hi = Math.min(hi, ceiling)

	const step = pickStep(lo, hi, ticks)
	lo = Math.floor(lo / step) * step
	hi = Math.ceil(hi / step) * step
	if (floor !== null) lo = Math.max(lo, floor)
	if (ceiling !== null) hi = Math.min(hi, ceiling)
	if (hi <= lo) hi = lo + step

	const count = Math.round((hi - lo) / step)
	// Rounded at each step: repeated addition of 2.5 drifts into 97.50000000001,
	// and a clamped edge carries the same noise into the domain itself.
	const out = Array.from({ length: count + 1 }, (_, i) => round(lo + i * step))

	return { min: round(lo), max: round(hi), ticks: out }
}

/**
 * The smallest round step whose gridlines still fit the target count.
 *
 * Snapping widens the domain, so the count is measured *after* snapping rather
 * than estimated from the raw span - estimating is what turned a 10-980 range
 * into a 0-1500 axis with four ticks.
 */
function pickStep(lo, hi, ticks) {
	const span = hi - lo
	const magnitude = 10 ** Math.floor(Math.log10(span / Math.max(ticks - 1, 1)))

	for (let scale = magnitude; scale <= magnitude * 1000; scale *= 10) {
		for (const mult of STEPS) {
			const step = mult * scale
			const snapped = Math.ceil(hi / step) * step - Math.floor(lo / step) * step
			if (Math.round(snapped / step) <= ticks + 1) return step
		}
	}

	return span / Math.max(ticks - 1, 1)
}

/** Trim the float noise that repeated addition introduces. */
function round(value) {
	return Math.round(value * 1e6) / 1e6
}

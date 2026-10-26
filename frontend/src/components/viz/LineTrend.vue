<template>
	<figure :class="bare ? '' : 'fm-card p-4'">
		<figcaption v-if="!bare" class="mb-1">
			<h3 class="fm-viz-title" :style="{ color: ink }">{{ title }}</h3>
			<p v-if="subtitle" class="fm-viz-subtitle" :style="{ color: inkSecondary }">{{ subtitle }}</p>
		</figcaption>

		<p v-if="!points.length" class="fm-viz-empty" :style="{ color: inkSecondary }">
			No completed runs yet.
		</p>

		<template v-else>
			<!-- One series, so the title names it and no legend box is needed;
			     the target is a labelled reference line, not a second series. -->
			<div class="relative hidden sm:block" @pointerleave="active = null">
				<!-- height:auto with an explicit aspect-ratio, so the plot fills
				     the card instead of being letterboxed inside a fixed height. -->
				<svg
					:viewBox="`0 0 ${W} ${H}`"
					class="w-full"
					:style="{ aspectRatio: `${W} / ${H}`, height: 'auto' }"
					preserveAspectRatio="xMidYMid meet"
					role="img"
					:aria-label="ariaLabel"
					@pointermove="onMove"
				>
					<!-- recessive gridlines -->
					<g>
						<line
							v-for="tick in ticks"
							:key="`g${tick.value}`"
							:x1="PAD.l"
							:x2="W - PAD.r"
							:y1="tick.y"
							:y2="tick.y"
							:stroke="grid"
							stroke-width="1"
						/>
						<text
							v-for="tick in ticks"
							:key="`t${tick.value}`"
							:x="PAD.l - 6"
							:y="tick.y + 3"
							text-anchor="end"
							font-size="10"
							:fill="inkSecondary"
							style="font-variant-numeric: tabular-nums"
						>
							{{ tick.label }}%
						</text>
					</g>

					<!-- Target reference line. Dashed deliberately: this is a
					     threshold, not a gridline, and must not read as one. -->
					<template v-if="targetY !== null">
						<line
							:x1="PAD.l"
							:x2="W - PAD.r"
							:y1="targetY"
							:y2="targetY"
							:stroke="axis"
							stroke-width="1"
							stroke-dasharray="4 3"
						/>
						<text
							:x="W - PAD.r"
							:y="targetY - 5"
							text-anchor="end"
							font-size="10"
							:fill="inkSecondary"
						>
							Planned {{ target }}%
						</text>
					</template>

					<!-- Area wash: the series hue at 10%, so the line carries
					     weight without the fill becoming a block. -->
					<path :d="areaPath" :fill="seriesColor" fill-opacity="0.1" />

					<!-- baseline -->
					<line
						:x1="PAD.l"
						:x2="W - PAD.r"
						:y1="H - PAD.b"
						:y2="H - PAD.b"
						:stroke="axis"
						stroke-width="1"
					/>

					<!-- 2px line -->
					<polyline
						:points="polyline"
						fill="none"
						:stroke="seriesColor"
						stroke-width="2"
						stroke-linejoin="round"
						stroke-linecap="round"
					/>

					<!-- markers: >=8px, with a 2px surface ring so overlaps stay readable -->
					<g v-for="point in points" :key="point.label">
						<circle
							:cx="point.x"
							:cy="point.y"
							:r="point.flagged ? 5 : 4.5"
							:fill="point.flagged ? flagColor : seriesColor"
							:stroke="ringColor"
							stroke-width="2"
						/>
						<!-- Selective direct labels: the latest run and any
						     flagged one. A flagged dip is labelled below its own
						     marker, so the text never lands on the line into it. -->
						<text
							v-if="point.labelled"
							:x="point.labelX"
							:y="point.labelY"
							:text-anchor="point.labelAnchor"
							font-size="10"
							:font-weight="point.flagged ? 600 : 400"
							:fill="point.flagged ? flagColor : inkSecondary"
							style="font-variant-numeric: tabular-nums"
						>
							{{ point.actual }}%
						</text>
					</g>

					<!-- x-axis: which run each point is. Thinned rather than
					     crowded - every label would overlap past about eight
					     points, and an unreadable label is worse than none. -->
					<text
						v-for="point in axisLabels"
						:key="`x${point.label}`"
						:x="point.x"
						:y="H - PAD.b + 15"
						text-anchor="middle"
						font-size="10"
						:fill="inkSecondary"
					>
						{{ point.short }}
					</text>

					<!-- crosshair -->
					<line
						v-if="active"
						:x1="active.x"
						:x2="active.x"
						:y1="PAD.t"
						:y2="H - PAD.b"
						:stroke="axis"
						stroke-width="1"
					/>
				</svg>

				<div
					v-if="active"
					class="pointer-events-none absolute z-10 rounded-lg px-2.5 py-1.5 text-xs shadow-lg"
					:style="tooltipStyle"
					role="status"
				>
					<p class="font-semibold">{{ active.item }}</p>
					<p :style="{ color: 'var(--fm-muted)' }">{{ active.label }} · {{ active.on }}</p>
					<p class="mt-0.5">
						Actual <span class="font-semibold fm-num">{{ active.actual }}%</span>
						<span :style="{ color: 'var(--fm-muted)' }"> · planned {{ active.planned }}%</span>
					</p>
					<p v-if="active.flagged" class="font-medium" :style="{ color: 'var(--viz-critical)' }">
						Variance outside tolerance
					</p>
				</div>
			</div>

			<!-- On a phone the plot is hidden and this table IS the chart: a
			     12-point series squeezed into 330px is not a readable chart,
			     and shrinking it would only pretend otherwise. -->
			<div class="sm:hidden" :style="{ color: ink }">
				<table class="w-full text-left text-xs">
					<caption class="sr-only">{{ title }}</caption>
					<thead>
						<tr :style="{ borderBottom: `1px solid ${rule}` }">
							<th scope="col" class="py-1 pr-2 font-medium" :style="{ color: inkSecondary }">Run</th>
							<th scope="col" class="py-1 pr-2 font-medium" :style="{ color: inkSecondary }">Actual %</th>
							<th scope="col" class="py-1 font-medium" :style="{ color: inkSecondary }">Planned %</th>
						</tr>
					</thead>
					<tbody class="fm-num">
						<tr v-for="row in series" :key="`m${row.label}`" :style="{ borderBottom: `1px solid ${rule}` }">
							<td class="py-1 pr-2">
								<span class="block">{{ row.item }}</span>
								<span class="text-[11px]" :style="{ color: inkSecondary }">{{ row.label }}</span>
							</td>
							<td class="py-1 pr-2 font-semibold"
								:style="{ color: row.flagged ? flagColor : ink }">
								{{ row.actual }}
								<span v-if="row.flagged" class="block text-[11px] font-normal">flagged</span>
							</td>
							<td class="py-1">{{ row.planned }}</td>
						</tr>
					</tbody>
				</table>
			</div>

			<!-- Table view on wider screens: the documented relief for a
			     contrast WARN, and the accessible equivalent of the plot. -->
			<details class="mt-2 hidden sm:block">
				<summary class="cursor-pointer text-xs" :style="{ color: inkSecondary }">
					View as table
				</summary>
				<table class="mt-2 w-full text-left text-xs">
					<caption class="sr-only">{{ title }}</caption>
					<thead>
						<tr :style="{ borderBottom: `1px solid ${rule}` }">
							<th scope="col" class="py-1 pr-3 font-medium" :style="{ color: inkSecondary }">Run</th>
							<th scope="col" class="py-1 pr-3 font-medium">Item</th>
							<th scope="col" class="py-1 pr-3 font-medium">Actual %</th>
							<th scope="col" class="py-1 font-medium">Planned %</th>
						</tr>
					</thead>
					<tbody class="fm-num">
						<tr v-for="row in series" :key="row.label" :style="{ borderBottom: `1px solid ${rule}` }">
							<td class="py-1 pr-3">{{ row.label }}</td>
							<td class="py-1 pr-3">{{ row.item }}</td>
							<td class="py-1 pr-3">{{ row.actual }}</td>
							<td class="py-1">{{ row.planned }}</td>
						</tr>
					</tbody>
				</table>
			</details>
		</template>
	</figure>
</template>

<script setup>
import { computed, ref } from 'vue'

import { niceScale } from '@/utils/scale'

const props = defineProps({
	title: { type: String, default: 'Yield trend' },
	subtitle: { type: String, default: '' },
	series: { type: Array, default: () => [] },
	// 'surface' renders on a white card; 'hero' on the dark performance panel.
	// Both colour sets are validated against their own surface.
	variant: { type: String, default: 'surface' },
	bare: Boolean,
})

const onHero = computed(() => props.variant === 'hero')
const ink = computed(() => (onHero.value ? 'var(--viz-hero-ink)' : 'var(--viz-ink)'))
const inkSecondary = computed(() =>
	onHero.value ? 'var(--viz-hero-ink-secondary)' : 'var(--viz-ink-secondary)'
)
const grid = computed(() => (onHero.value ? 'var(--viz-hero-grid)' : 'var(--viz-grid)'))
const axis = computed(() => (onHero.value ? 'var(--viz-hero-axis)' : 'var(--viz-axis)'))
const seriesColor = computed(() => (onHero.value ? 'var(--viz-hero-series)' : 'var(--viz-series-1)'))
const flagColor = computed(() => (onHero.value ? 'var(--viz-hero-flag)' : 'var(--viz-critical)'))
const ringColor = computed(() => (onHero.value ? 'var(--fm-hero)' : 'var(--viz-surface)'))
const rule = computed(() => (onHero.value ? 'rgba(255,255,255,0.16)' : 'var(--viz-grid)'))

// The SVG stretches to its container, so the viewBox sets the effective text
// size: too narrow a box magnifies every label, too wide a box shrinks it.
// The hero panel is a narrower column than a full-width card, so it gets its
// own box rather than inheriting one tuned for a different width.
const W = computed(() => (onHero.value ? 620 : 960))
const H = computed(() => (onHero.value ? 230 : 250))
// The bottom pad carries the x-axis band. Without it the run labels were
// simply never drawn: the plot filled the box and there was nowhere to put
// them, so the chart could not say which run was which.
const PAD = computed(() =>
	onHero.value ? { t: 22, r: 16, b: 40, l: 40 } : { t: 24, r: 20, b: 42, l: 46 }
)

const active = ref(null)

const target = computed(() => {
	const planned = props.series.map((row) => Number(row.planned)).filter(Boolean)
	if (!planned.length) return null
	return Math.round(planned.reduce((a, b) => a + b, 0) / planned.length)
})

/*
 * The planned line is the thing every run is read against, so it belongs in the
 * domain - but as its edge, not as a value to pad beyond. Capping the ceiling at
 * the target is what stops a 92-97% series from being drawn inside an 85-105%
 * band, where every run looks the same.
 */
const scale = computed(() => {
	const values = props.series.map((row) => Number(row.actual)).filter(Number.isFinite)
	if (!values.length) return niceScale(0, 100, { ticks: 5 })

	const lo = Math.min(...values)
	const hi = Math.max(...values, target.value ?? -Infinity)
	const overTarget = target.value !== null && Math.max(...values) > target.value

	return niceScale(lo, hi, {
		ticks: 5,
		floor: 0,
		ceiling: overTarget ? null : target.value,
	})
})

const yFor = (value) => {
	const { min, max } = scale.value
	const ratio = (Number(value) - min) / (max - min)
	return H.value - PAD.value.b - ratio * (H.value - PAD.value.t - PAD.value.b)
}

const points = computed(() => {
	const count = props.series.length
	const span = W.value - PAD.value.l - PAD.value.r
	const rows = props.series.map((row, index) => ({
		...row,
		x: count === 1 ? PAD.value.l + span / 2 : PAD.value.l + (index / (count - 1)) * span,
		y: yFor(row.actual),
	}))

	return rows.map((row, index) => {
		// Selective by design: the latest run and every flagged one. Labelling
		// the first point too only crowds the left edge, and the axis already
		// carries it.
		const labelled = index === rows.length - 1 || Boolean(row.flagged)
		// A dip labelled above its marker lands on the line coming into it.
		const prev = rows[index - 1]
		const next = rows[index + 1]
		const isTrough =
			(!prev || prev.y < row.y) && (!next || next.y < row.y)
		const below = Boolean(row.flagged) && isTrough

		// The end points sit against the plot frame, so their labels go beside
		// the marker rather than above it, where they would crowd the axis.
		const first = index === 0
		const last = index === rows.length - 1

		return {
			...row,
			labelled,
			labelY: below ? row.y + 16 : first || last ? row.y + 4 : row.y - 11,
			labelX: first ? row.x + 9 : last ? row.x - 9 : row.x,
			labelAnchor: first ? 'start' : last ? 'end' : 'middle',
		}
	})
})

const polyline = computed(() => points.value.map((p) => `${p.x},${p.y}`).join(' '))

/**
 * Run labels along the bottom, thinned to what fits.
 *
 * A work order name is long ("MFG-WO-2026-00031"), so only its distinctive tail
 * is shown - the part an operator actually reads off the board.
 */
const axisLabels = computed(() => {
	const rows = points.value
	if (!rows.length) return []

	const room = (W.value - PAD.value.l - PAD.value.r) / 54
	const step = Math.max(1, Math.ceil(rows.length / Math.max(room, 1)))

	return rows
		.filter((_row, index) => index % step === 0 || index === rows.length - 1)
		.map((row) => ({ ...row, short: shorten(row.label) }))
})

function shorten(label) {
	if (!label) return ''
	const tail = String(label).split('-').pop()
	// A bare sequence number is ambiguous on its own; keep a hint of the prefix.
	return tail && tail.length <= 6 ? `#${tail.replace(/^0+/, '') || tail}` : String(label).slice(-8)
}

const areaPath = computed(() => {
	if (!points.value.length) return ''
	const base = H.value - PAD.value.b
	const first = points.value[0]
	const last = points.value[points.value.length - 1]
	const line = points.value.map((p) => `L${p.x},${p.y}`).join(' ')
	return `M${first.x},${base} ${line} L${last.x},${base} Z`
})

const ticks = computed(() =>
	scale.value.ticks.map((value) => ({
		value,
		// Trailing ".0" on a whole-number axis is noise.
		label: Number.isInteger(value) ? value : value.toFixed(1),
		y: yFor(value),
	}))
)

const targetY = computed(() => {
	if (target.value === null) return null
	const { min, max } = scale.value
	// Off-scale targets would be drawn outside the plot frame.
	if (target.value < min || target.value > max) return null
	return yFor(target.value)
})

const ariaLabel = computed(() => {
	if (!props.series.length) return props.title
	const last = props.series[props.series.length - 1]
	return `${props.title}: ${props.series.length} runs, latest actual yield ${last.actual} percent`
})

const tooltipStyle = computed(() => {
	if (!active.value) return {}

	const left = (active.value.x / W.value) * 100
	const topRatio = active.value.y / H.value
	// Hung off the hovered marker rather than pinned to the top of the plot,
	// where it sat on the "Planned" reference label. It flips above the point
	// in the lower half so it never runs out of the card.
	const top = topRatio > 0.55 ? `${topRatio * 100 - 34}%` : `${topRatio * 100 + 8}%`

	return {
		left: `${Math.min(Math.max(left, 2), 66)}%`,
		top,
		background: 'var(--fm-surface)',
		color: 'var(--fm-ink)',
		border: '1px solid var(--fm-border)',
	}
})

function onMove(event) {
	if (!points.value.length) return
	const rect = event.currentTarget.getBoundingClientRect()
	const x = ((event.clientX - rect.left) / rect.width) * W.value
	// Hit target is the nearest point, not the mark itself, so it stays
	// comfortable on a touch screen.
	let nearest = points.value[0]
	for (const point of points.value) {
		if (Math.abs(point.x - x) < Math.abs(nearest.x - x)) nearest = point
	}
	active.value = nearest
}
</script>

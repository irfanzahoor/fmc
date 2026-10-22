<template>
	<figure class="fm-card p-4">
		<figcaption class="mb-1">
			<h3 class="text-sm font-semibold" :style="{ color: 'var(--viz-ink)' }">{{ title }}</h3>
			<p v-if="subtitle" class="text-xs" :style="{ color: 'var(--viz-ink-secondary)' }">{{ subtitle }}</p>
		</figcaption>

		<p v-if="!points.length" class="py-10 text-center text-sm text-gray-500">
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
							stroke="var(--viz-grid)"
							stroke-width="1"
						/>
						<text
							v-for="tick in ticks"
							:key="`t${tick.value}`"
							:x="PAD.l - 6"
							:y="tick.y + 3"
							text-anchor="end"
							font-size="10"
							fill="var(--viz-muted)"
							style="font-variant-numeric: tabular-nums"
						>
							{{ tick.value }}%
						</text>
					</g>

					<!-- target reference line, labelled in words -->
					<template v-if="targetY !== null">
						<line
							:x1="PAD.l"
							:x2="W - PAD.r"
							:y1="targetY"
							:y2="targetY"
							stroke="var(--viz-axis)"
							stroke-width="1"
							stroke-dasharray="4 3"
						/>
						<text
							:x="W - PAD.r"
							:y="targetY - 4"
							text-anchor="end"
							font-size="10"
							fill="var(--viz-ink-secondary)"
						>
							Planned {{ target }}%
						</text>
					</template>

					<!-- baseline -->
					<line
						:x1="PAD.l"
						:x2="W - PAD.r"
						:y1="H - PAD.b"
						:y2="H - PAD.b"
						stroke="var(--viz-axis)"
						stroke-width="1"
					/>

					<!-- 2px line -->
					<polyline
						:points="polyline"
						fill="none"
						stroke="var(--viz-series-1)"
						stroke-width="2"
						stroke-linejoin="round"
						stroke-linecap="round"
					/>

					<!-- markers: >=8px, with a 2px surface ring so overlaps stay readable -->
					<g v-for="(point, index) in points" :key="point.label">
						<circle
							:cx="point.x"
							:cy="point.y"
							r="4.5"
							:fill="point.flagged ? 'var(--viz-critical)' : 'var(--viz-series-1)'"
							stroke="var(--viz-surface)"
							stroke-width="2"
						/>
						<!-- Selective direct labels: first, last and any flagged run. -->
						<text
							v-if="index === 0 || index === points.length - 1 || point.flagged"
							:x="point.x"
							:y="point.y - 10"
							text-anchor="middle"
							font-size="10"
							:fill="point.flagged ? 'var(--viz-critical)' : 'var(--viz-ink-secondary)'"
						>
							{{ point.actual }}%
						</text>
					</g>

					<!-- crosshair -->
					<line
						v-if="active"
						:x1="active.x"
						:x2="active.x"
						:y1="PAD.t"
						:y2="H - PAD.b"
						stroke="var(--viz-axis)"
						stroke-width="1"
					/>
				</svg>

				<div
					v-if="active"
					class="pointer-events-none absolute z-10 rounded-md border border-gray-200 bg-white px-2 py-1 text-xs shadow-md"
					:style="tooltipStyle"
					role="status"
				>
					<p class="font-medium">{{ active.item }}</p>
					<p class="text-gray-600">{{ active.label }} · {{ active.on }}</p>
					<p>
						Actual <span class="font-semibold">{{ active.actual }}%</span>
						· planned {{ active.planned }}%
					</p>
					<p v-if="active.flagged" :style="{ color: 'var(--viz-critical)' }">
						Variance outside tolerance
					</p>
				</div>
			</div>

			<!-- On a phone the plot is hidden and this table IS the chart: a
			     12-point series squeezed into 330px is not a readable chart,
			     and shrinking it would only pretend otherwise. -->
			<div class="sm:hidden">
				<table class="w-full text-left text-xs">
					<caption class="sr-only">{{ title }}</caption>
					<thead>
						<tr class="border-b border-gray-200">
							<th scope="col" class="py-1 pr-2 font-medium">Run</th>
							<th scope="col" class="py-1 pr-2 font-medium">Actual %</th>
							<th scope="col" class="py-1 font-medium">Planned %</th>
						</tr>
					</thead>
					<tbody style="font-variant-numeric: tabular-nums">
						<tr v-for="row in series" :key="`m${row.label}`" class="border-b border-gray-100">
							<td class="py-1 pr-2">
								<span class="block">{{ row.item }}</span>
								<span class="text-[11px] text-gray-500">{{ row.label }}</span>
							</td>
							<td class="py-1 pr-2 font-semibold"
								:style="{ color: row.flagged ? 'var(--viz-critical)' : 'var(--viz-ink)' }">
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
				<summary class="cursor-pointer text-xs" :style="{ color: 'var(--viz-ink-secondary)' }">
					View as table
				</summary>
				<table class="mt-2 w-full text-left text-xs">
					<caption class="sr-only">{{ title }}</caption>
					<thead>
						<tr class="border-b border-gray-200">
							<th scope="col" class="py-1 pr-3 font-medium">Run</th>
							<th scope="col" class="py-1 pr-3 font-medium">Item</th>
							<th scope="col" class="py-1 pr-3 font-medium">Actual %</th>
							<th scope="col" class="py-1 font-medium">Planned %</th>
						</tr>
					</thead>
					<tbody style="font-variant-numeric: tabular-nums">
						<tr v-for="row in series" :key="row.label" class="border-b border-gray-100">
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

const props = defineProps({
	title: { type: String, default: 'Yield trend' },
	subtitle: { type: String, default: '' },
	series: { type: Array, default: () => [] },
})

// A wide, flat viewBox: the SVG stretches to the card, so a narrow box would
// magnify every label. 960x260 keeps axis text near its intended size.
const W = 960
const H = 260
const PAD = { t: 22, r: 20, b: 28, l: 46 }

const active = ref(null)

const target = computed(() => {
	const planned = props.series.map((row) => Number(row.planned)).filter(Boolean)
	if (!planned.length) return null
	return Math.round(planned.reduce((a, b) => a + b, 0) / planned.length)
})

const domain = computed(() => {
	const values = props.series.map((row) => Number(row.actual))
	if (target.value) values.push(target.value)
	if (!values.length) return { min: 0, max: 100 }

	const min = Math.min(...values)
	const max = Math.max(...values)
	// Pad the band so the line never sits on the frame, and never imply a
	// zero baseline we did not measure.
	const lo = Math.max(0, Math.floor((min - 4) / 5) * 5)
	const hi = Math.min(110, Math.ceil((max + 4) / 5) * 5)
	return { min: lo, max: hi === lo ? lo + 5 : hi }
})

const yFor = (value) => {
	const { min, max } = domain.value
	const ratio = (Number(value) - min) / (max - min)
	return H - PAD.b - ratio * (H - PAD.t - PAD.b)
}

const points = computed(() => {
	const count = props.series.length
	const span = W - PAD.l - PAD.r
	return props.series.map((row, index) => ({
		...row,
		x: count === 1 ? PAD.l + span / 2 : PAD.l + (index / (count - 1)) * span,
		y: yFor(row.actual),
	}))
})

const polyline = computed(() => points.value.map((p) => `${p.x},${p.y}`).join(' '))

const ticks = computed(() => {
	const { min, max } = domain.value
	const step = (max - min) / 4
	return Array.from({ length: 5 }, (_, i) => {
		const value = Math.round(min + i * step)
		return { value, y: yFor(value) }
	})
})

const targetY = computed(() => (target.value === null ? null : yFor(target.value)))

const ariaLabel = computed(() => {
	if (!props.series.length) return props.title
	const last = props.series[props.series.length - 1]
	return `${props.title}: ${props.series.length} runs, latest actual yield ${last.actual} percent`
})

const tooltipStyle = computed(() => {
	if (!active.value) return {}
	const left = (active.value.x / W) * 100
	return {
		left: `${Math.min(Math.max(left, 4), 72)}%`,
		top: '4px',
	}
})

function onMove(event) {
	if (!points.value.length) return
	const rect = event.currentTarget.getBoundingClientRect()
	const x = ((event.clientX - rect.left) / rect.width) * W
	// Hit target is the nearest point, not the mark itself, so it stays
	// comfortable on a touch screen.
	let nearest = points.value[0]
	for (const point of points.value) {
		if (Math.abs(point.x - x) < Math.abs(nearest.x - x)) nearest = point
	}
	active.value = nearest
}
</script>

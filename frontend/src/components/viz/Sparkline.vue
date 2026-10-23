<template>
	<svg
		v-if="points.length > 1"
		:viewBox="`0 0 ${W} ${H}`"
		class="w-full"
		:style="{ aspectRatio: `${W} / ${H}`, height: 'auto' }"
		preserveAspectRatio="xMidYMid meet"
		role="img"
		:aria-label="ariaLabel"
	>
		<!-- The run of history is context, so it stays in the de-emphasis hue;
		     only the latest point wears the accent. -->
		<polyline
			:points="polyline"
			fill="none"
			:stroke="trackColor"
			stroke-width="2"
			stroke-linejoin="round"
			stroke-linecap="round"
		/>
		<circle :cx="last.x" :cy="last.y" :r="R" :fill="accentColor" />
	</svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
	/** Plain numbers, oldest first. */
	values: { type: Array, default: () => [] },
	label: { type: String, default: 'Recent trend' },
	accent: { type: String, default: 'var(--viz-series-1)' },
	track: { type: String, default: 'var(--viz-axis)' },
})

/*
 * A uniform scale ("meet"), not a stretched one.
 *
 * With preserveAspectRatio="none" the box stretches to the card's width, which
 * also stretches the end dot into an ellipse and clips it against the right
 * edge. The box keeps a realistic aspect instead, and the dot is inset by its
 * own radius so it stays whole.
 */
const W = 180
const H = 40
const R = 3.5

const accentColor = computed(() => props.accent)
const trackColor = computed(() => props.track)

const series = computed(() =>
	props.values.map(Number).filter(Number.isFinite).slice(-12)
)

const points = computed(() => {
	const rows = series.value
	if (rows.length < 2) return []

	const min = Math.min(...rows)
	const max = Math.max(...rows)
	// A flat run would divide by zero; draw it down the middle instead.
	const span = max - min || 1
	const pad = R + 2

	const left = R
	const right = W - R

	return rows.map((value, index) => ({
		x: left + (index / (rows.length - 1)) * (right - left),
		y: H - pad - ((value - min) / span) * (H - pad * 2),
	}))
})

const polyline = computed(() => points.value.map((p) => `${p.x},${p.y}`).join(' '))
const last = computed(() => points.value[points.value.length - 1] || { x: 0, y: 0 })

const ariaLabel = computed(() => {
	const rows = series.value
	if (rows.length < 2) return props.label
	return `${props.label}: ${rows.length} points, from ${rows[0]} to ${rows[rows.length - 1]}`
})
</script>

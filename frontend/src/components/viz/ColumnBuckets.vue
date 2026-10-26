<template>
	<figure :class="bare ? '' : 'fm-card p-4'">
		<figcaption class="mb-2">
			<h3 class="fm-viz-title">{{ title }}</h3>
			<p v-if="subtitle" class="fm-viz-subtitle">{{ subtitle }}</p>
		</figcaption>

		<p v-if="!columns.length" class="fm-viz-empty">
			{{ emptyText }}
		</p>

		<!--
			Columns, not horizontal bars: these buckets are an ORDERED time
			scale, and time reads left to right. The labels are short enough to
			sit under a column without rotating, which is the usual reason to
			lay a ranking on its side.

			Every column is direct-labelled on its cap, so there is no y-axis to
			read - four columns is few enough that labelling each one is the
			sparing choice, not a flood.

			Each column sits in a track running the full height of the plot.
			The track is what the column is a fraction *of*, so a bucket holding
			two batches out of a maximum of two no longer has to be read against
			nothing; it also stops three columns in a wide card reading as a
			chart with its middle missing.
		-->
		<div v-else>
			<!--
				The plot is capped rather than stretched. Laying bands out with
				flex-1 alone divides whatever width the card happens to have, so
				in a wide card three buckets became three 72px columns floating
				at 300px centres. A column chart's proportions belong to the
				chart, not to its container.
			-->
			<ul class="flex items-stretch gap-2" :style="{ height: `${PLOT}px`, maxWidth: plotWidth }">
				<li v-for="column in columns" :key="column.label" class="min-w-0 flex-1">
					<button
						type="button"
						class="relative flex h-full w-full flex-col justify-end overflow-hidden rounded-md transition-[filter] motion-reduce:transition-none"
						:style="{
							background: 'var(--viz-plane)',
							filter: active && active !== column.label ? 'opacity(0.55)' : 'none',
						}"
						:aria-label="`${column.label}: ${column.value} ${unitLabel}`"
						@pointerenter="active = column.label"
						@pointerleave="active = null"
						@focus="active = column.label"
						@blur="active = null"
					>
						<span
							class="fm-num mb-1 text-center text-xs font-semibold"
							:style="{ color: column.zero ? 'var(--viz-ink-secondary)' : 'var(--viz-ink)' }"
						>
							{{ column.value }}
						</span>

						<span
							class="block w-full"
							:style="{ height: `${column.height}px`, background: column.color }"
						/>
					</button>
				</li>
			</ul>

			<!-- Baseline: a solid hairline, one step off the surface. It stops
			     where the plot stops; a rule running on past the last column was
			     most of what made a short chart look unfinished. -->
			<div :style="{ borderTop: '1px solid var(--viz-axis)', maxWidth: plotWidth }" />

			<ul class="flex gap-2" :style="{ maxWidth: plotWidth }">
				<li v-for="column in columns" :key="`l${column.label}`" class="min-w-0 flex-1">
					<p
						class="mt-1.5 text-center text-[11px] leading-tight"
						:style="{ color: 'var(--viz-ink-secondary)' }"
					>
						{{ column.label }}
					</p>
				</li>
			</ul>

			<p v-if="footnote" class="mt-3 text-[11px]" :style="{ color: 'var(--viz-ink-secondary)' }">
				{{ footnote }}
			</p>
		</div>
	</figure>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
	title: { type: String, required: true },
	subtitle: { type: String, default: '' },
	/** `{ label, value }` in scale order - never re-sorted. */
	rows: { type: Array, default: () => [] },
	unitLabel: { type: String, default: '' },
	emptyText: { type: String, default: 'Nothing to show yet.' },
	footnote: { type: String, default: '' },
	bare: Boolean,
	/** Ordered scale, so the ramp steps with position, not with magnitude. */
	ramp: {
		type: Array,
		default: () => [
			'var(--viz-ordinal-4)',
			'var(--viz-ordinal-3)',
			'var(--viz-ordinal-2)',
			'var(--viz-ordinal-1)',
		],
	},
})

const PLOT = 150

/* The widest a band may get, not a fixed width. The bands still divide the
   card, so a narrow card simply makes them narrower; the cap is only there to
   stop a wide card stretching three buckets into three columns floating at
   300px centres, which is what flex-1 on its own did. A column fills its band,
   so this caps the column too. */
const BAND = 110
const active = ref(null)

const columns = computed(() => {
	const rows = props.rows
	if (!rows.length) return []

	const max = Math.max(...rows.map((row) => Number(row.value) || 0), 0)

	return rows.map((row, index) => {
		const value = Number(row.value) || 0
		return {
			label: row.label,
			value,
			zero: value === 0,
			// A real zero still gets a visible stub, so the bucket is not
			// mistaken for one that was never measured.
			height: max > 0 ? Math.max((value / max) * (PLOT - 24), value > 0 ? 6 : 2) : 2,
			// A row's own colour wins. Stepping the ramp by row index repaints
			// the survivors when a bucket is empty and drops out - the colour
			// has to follow the bucket, not its position in today's rows.
			color: row.color || props.ramp[Math.min(index, props.ramp.length - 1)],
		}
	})
})

const plotWidth = computed(() => `${columns.value.length * BAND}px`)
</script>

<template>
	<figure class="fm-card p-4">
		<figcaption class="mb-2">
			<h3 class="text-sm font-semibold" :style="{ color: 'var(--viz-ink)' }">{{ title }}</h3>
			<p v-if="subtitle" class="text-xs" :style="{ color: 'var(--viz-ink-secondary)' }">{{ subtitle }}</p>
		</figcaption>

		<p v-if="!rows.length" class="py-10 text-center text-sm text-gray-500">{{ emptyText }}</p>

		<!-- Horizontal bars: long item names read without rotating labels, and
		     length already carries magnitude so one hue is enough.

		     Bars are scaled WITHIN a unit group, never across units. Comparing
		     1,842 kg against 24,000 packs on one length axis would be
		     arithmetic on incompatible units, and would read as "packs dwarf
		     everything" when the two measure different things. -->
		<div v-else class="space-y-4">
			<div v-for="group in groups" :key="group.unit">
				<p
					v-if="groups.length > 1"
					class="fm-label mb-1.5 border-b border-gray-100 pb-1"
				>
					{{ group.unit || 'Unitless' }}
				</p>

				<ul class="space-y-2.5">
					<li v-for="row in group.rows" :key="row.key">
						<div class="flex items-baseline justify-between gap-2 text-xs">
							<span class="truncate" :style="{ color: 'var(--viz-ink)' }">{{ row.label }}</span>
							<span
								class="shrink-0 font-semibold"
								style="font-variant-numeric: tabular-nums"
								:style="{ color: 'var(--viz-ink)' }"
							>
								{{ format(row.value) }}<span class="ml-0.5 font-normal text-gray-500">{{ row.unitLabel }}</span>
							</span>
						</div>

						<div
							class="mt-1 h-2.5 w-full overflow-hidden rounded-full"
							:style="{ background: 'var(--viz-grid)' }"
							role="img"
							:aria-label="`${row.label}: ${format(row.value)} ${row.unitLabel}`"
						>
							<!-- 4px rounded data-end, anchored to the baseline at the left. -->
							<div
								class="h-full rounded-full transition-[width] duration-500 motion-reduce:transition-none"
								:style="{ width: `${row.percent}%`, background: row.color }"
							/>
						</div>

						<p v-if="row.note" class="mt-0.5 text-[11px]" :style="{ color: 'var(--viz-ink-secondary)' }">
							{{ row.note }}
						</p>
					</li>
				</ul>
			</div>
		</div>
	</figure>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
	title: { type: String, required: true },
	subtitle: { type: String, default: '' },
	rows: { type: Array, default: () => [] },
	emptyText: { type: String, default: 'Nothing to show yet.' },
	decimals: { type: Number, default: 1 },
	barColor: { type: String, default: 'var(--viz-series-1)' },
})

const format = (value) =>
	Number(value || 0).toLocaleString(undefined, {
		minimumFractionDigits: 0,
		maximumFractionDigits: props.decimals,
	})

/** Rows bucketed by unit, each bucket scaled against its own maximum. */
const groups = computed(() => {
	const buckets = new Map()

	for (const [index, row] of props.rows.entries()) {
		const unit = row.unit || ''
		if (!buckets.has(unit)) buckets.set(unit, [])
		buckets.get(unit).push({ ...row, _index: index })
	}

	return [...buckets.entries()].map(([unit, rows]) => {
		const max = Math.max(...rows.map((row) => Number(row.value) || 0), 0)
		return {
			unit,
			rows: rows.map((row) => ({
				key: row.key || row.item_code || row.label || row._index,
				label: row.label,
				value: Number(row.value) || 0,
				unitLabel: unit ? ` ${unit}` : '',
				note: row.note || '',
				color: row.color || props.barColor,
				percent: max > 0 ? Math.max((Number(row.value) / max) * 100, 1.5) : 0,
			})),
		}
	})
})
</script>

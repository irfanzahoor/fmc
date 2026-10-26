<template>
	<figure class="fm-card p-4">
		<figcaption class="mb-2 flex flex-wrap items-start justify-between gap-2">
			<div>
				<h3 class="fm-viz-title">{{ title }}</h3>
				<p v-if="subtitle" class="fm-viz-subtitle">{{ subtitle }}</p>
			</div>
			<!-- A card that summarises should say where the detail lives. -->
			<RouterLink
				v-if="to"
				:to="to"
				class="flex shrink-0 items-center gap-1 text-xs font-medium"
				:style="{ color: 'var(--fm-primary)' }"
			>
				{{ toLabel }}
				<ArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />
			</RouterLink>
		</figcaption>

		<p v-if="!rows.length" class="fm-viz-empty">
			{{ emptyText }}
		</p>

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
					class="fm-label mb-1.5 border-b pb-1"
					:style="{ borderColor: 'var(--viz-grid)' }"
				>
					{{ group.label }}
				</p>

				<!-- A single row is not a ranking: one full-width bar says only
				     "this is 100% of itself". It reads as a figure instead. -->
				<div
					v-if="group.rows.length === 1"
					class="flex items-baseline justify-between gap-3 rounded-xl px-3 py-2.5"
					:style="{ background: 'var(--viz-plane)' }"
				>
					<span class="truncate text-sm" :style="{ color: 'var(--viz-ink)' }">
						{{ group.rows[0].label }}
						<span v-if="group.rows[0].note" class="block text-[11px]" :style="{ color: 'var(--viz-ink-secondary)' }">
							{{ group.rows[0].note }}
						</span>
					</span>
					<span class="shrink-0 text-lg font-semibold" :style="{ color: 'var(--viz-ink)' }">
						{{ format(group.rows[0].value) }}<span
							class="ml-1 text-xs font-normal"
							:style="{ color: 'var(--viz-ink-secondary)' }"
						>{{ group.rows[0].unitLabel }}</span>
					</span>
				</div>

				<ul v-else class="space-y-2.5">
					<li
						v-for="row in group.rows"
						:key="row.key"
						class="group rounded-md px-1 py-0.5 transition-colors"
						:class="active === row.key ? 'fm-bar-hover' : ''"
						tabindex="0"
						@pointerenter="active = row.key"
						@pointerleave="active = null"
						@focus="active = row.key"
						@blur="active = null"
					>
						<div class="flex items-baseline justify-between gap-2 text-xs">
							<span class="truncate" :style="{ color: 'var(--viz-ink)' }">{{ row.label }}</span>
							<span class="fm-num shrink-0 font-semibold" :style="{ color: 'var(--viz-ink)' }">
								{{ format(row.value) }}<span
									class="ml-0.5 font-normal"
									:style="{ color: 'var(--viz-ink-secondary)' }"
								>{{ row.unitLabel }}</span>
							</span>
						</div>

						<div
							class="mt-1 h-2.5 w-full overflow-hidden rounded-full"
							:style="{ background: 'var(--viz-grid)' }"
							role="img"
							:aria-label="`${row.label}: ${format(row.value)} ${row.unitLabel}, ${row.share}% of ${group.unit || 'the total'}`"
						>
							<!-- 4px rounded data-end, anchored to the baseline at the left. -->
							<div
								class="h-full rounded-full transition-[width] duration-500 motion-reduce:transition-none"
								:style="{ width: `${row.percent}%`, background: row.color }"
							/>
						</div>

						<p
							v-if="showShare || row.note"
							class="mt-0.5 flex items-center gap-1.5 text-[11px]"
							:style="{ color: 'var(--viz-ink-secondary)' }"
						>
							<span v-if="showShare" class="fm-num">{{ row.share }}% of group</span>
							<span v-if="showShare && row.note" aria-hidden="true">·</span>
							<span v-if="row.note" class="truncate">{{ row.note }}</span>
						</p>
					</li>
				</ul>
			</div>
		</div>
	</figure>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ArrowUpRight } from 'lucide-vue-next'
import { RouterLink } from 'vue-router'

const props = defineProps({
	title: { type: String, required: true },
	subtitle: { type: String, default: '' },
	rows: { type: Array, default: () => [] },
	emptyText: { type: String, default: 'Nothing to show yet.' },
	decimals: { type: Number, default: 1 },
	barColor: { type: String, default: 'var(--viz-series-1)' },
	// Off when the values are already shares - "12.3% ... 29% of group" reads
	// as two competing percentages of the same thing.
	showShare: { type: Boolean, default: true },
	// Off for an ORDERED scale. Expiry buckets run expired -> 90 days: sorting
	// them by count puts "31-90 days" first and makes the subtitle a lie.
	sorted: { type: Boolean, default: true },
	// Where the fuller version of this card lives, if there is one.
	to: { type: [Object, String], default: null },
	toLabel: { type: String, default: 'View insights' },
})

const active = ref(null)

/**
 * "Bulk production · Kg" rather than a bare "KG".
 *
 * The unit alone says nothing about what is being compared. When every row in
 * the group shares a material nature, that nature names the group; a mixed
 * group falls back to the unit, because naming it after one of its halves
 * would be wrong.
 */
const NATURE_LABEL = {
	'Bulk Blend': 'Bulk production',
	'Finished Good': 'Finished goods',
	'Raw Material': 'Raw materials',
	'Packaging Material': 'Packaging',
}

function groupLabel(rows, unit) {
	const natures = new Set(rows.map((row) => row.nature).filter(Boolean))
	const unitLabel = unit || 'Unitless'
	if (natures.size !== 1) return unitLabel

	const nature = NATURE_LABEL[[...natures][0]]
	return nature ? `${nature} · ${unitLabel}` : unitLabel
}

const format = (value) =>
	Number(value || 0).toLocaleString(undefined, {
		minimumFractionDigits: 0,
		maximumFractionDigits: props.decimals,
	})

/** Rows bucketed by unit, each bucket ranked and scaled against its own maximum. */
const groups = computed(() => {
	const buckets = new Map()

	for (const [index, row] of props.rows.entries()) {
		const unit = row.unit || ''
		if (!buckets.has(unit)) buckets.set(unit, [])
		buckets.get(unit).push({ ...row, _index: index })
	}

	return [...buckets.entries()].map(([unit, rows]) => {
		// A ranking chart has to be ranked: bars in arbitrary order make the
		// reader do the sorting the chart exists to do. An ordered scale keeps
		// the order it arrived in - that order is the information.
		const ordered = props.sorted
			? [...rows].sort((a, b) => (Number(b.value) || 0) - (Number(a.value) || 0))
			: [...rows]
		const max = Math.max(...ordered.map((row) => Number(row.value) || 0), 0)
		const total = ordered.reduce((sum, row) => sum + (Number(row.value) || 0), 0)

		return {
			unit,
			label: groupLabel(ordered, unit),
			rows: ordered.map((row) => ({
				key: row.key || row.item_code || row.label || row._index,
				label: row.label,
				value: Number(row.value) || 0,
				unitLabel: unit ? ` ${unit}` : '',
				note: row.note || '',
				color: row.color || props.barColor,
				percent: max > 0 ? Math.max((Number(row.value) / max) * 100, 1.5) : 0,
				// Length shows the comparison; the share says what it is worth.
				share: total > 0 ? Math.round((Number(row.value) / total) * 100) : 0,
			})),
		}
	})
})
</script>

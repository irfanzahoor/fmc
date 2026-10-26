<template>
	<figure class="fm-card p-4">
		<figcaption class="mb-3 flex flex-wrap items-start justify-between gap-2">
			<div>
				<h3 class="fm-viz-title">{{ title }}</h3>
				<p class="fm-viz-subtitle">{{ subtitle }}</p>
			</div>
			<span v-if="rows.length" class="fm-chip fm-chip-bad shrink-0">
				{{ rows.length }} {{ rows.length === 1 ? 'exception' : 'exceptions' }}
			</span>
		</figcaption>

		<!-- An empty exceptions table is good news, and should read as such
		     rather than as a table that failed to load. -->
		<div
			v-if="!rows.length"
			class="rounded-xl p-6 text-center"
			:style="{ background: 'var(--viz-plane)' }"
		>
			<CheckCircle class="mx-auto h-6 w-6" :style="{ color: 'var(--viz-good)' }" aria-hidden="true" />
			<p class="mt-2 text-sm font-medium" :style="{ color: 'var(--viz-ink)' }">
				Every completed run was inside tolerance.
			</p>
			<p class="mt-1 text-xs" :style="{ color: 'var(--viz-ink-secondary)' }">
				Nothing needs reviewing before the next run.
			</p>
		</div>

		<!-- Horizontal scroll on a narrow screen rather than a squeezed table:
		     six numeric columns do not fold usefully. -->
		<div v-else class="-mx-4 overflow-x-auto px-4">
			<table class="fm-table w-full min-w-[46rem] text-left text-sm">
				<caption class="sr-only">{{ title }}</caption>
				<thead>
					<tr>
						<th scope="col">Work order</th>
						<th scope="col">Product</th>
						<th scope="col" class="text-right">Input</th>
						<th scope="col" class="text-right">Good output</th>
						<th scope="col" class="text-right">Process loss</th>
						<th scope="col" class="text-right">Yield</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="row in rows" :key="row.work_order">
						<td>
							<span class="fm-id font-medium">{{ row.work_order }}</span>
							<span class="block text-[11px]" :style="{ color: 'var(--viz-ink-secondary)' }">
								{{ row.on }}
							</span>
						</td>
						<td class="max-w-[14rem] truncate">{{ row.item_name }}</td>
						<td class="fm-num text-right">{{ qty(row.input_qty, row.uom) }}</td>
						<td class="fm-num text-right">{{ qty(row.produced_qty, row.uom) }}</td>
						<td class="fm-num text-right">{{ qty(row.loss_qty, row.uom) }}</td>
						<td class="text-right">
							<span class="fm-chip fm-chip-bad fm-num">{{ row.yield_percent }}%</span>
							<span
								v-if="row.planned_percent"
								class="block text-[11px]"
								:style="{ color: 'var(--viz-ink-secondary)' }"
							>
								planned {{ row.planned_percent }}%
							</span>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
	</figure>
</template>

<script setup>
import { CheckCircle } from 'lucide-vue-next'

defineProps({
	title: { type: String, default: 'Completed-run review' },
	subtitle: { type: String, default: 'A focused view of flagged production records.' },
	rows: { type: Array, default: () => [] },
})

/** A quantity with its unit, or an em dash when it was never measured. */
function qty(value, uom) {
	if (value === null || value === undefined) return '—'
	const number = Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })
	return uom ? `${number} ${uom}` : number
}
</script>

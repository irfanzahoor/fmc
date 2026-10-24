<template>
	<div v-if="rows.length" class="mt-4">
		<p class="fm-label mb-2">{{ label }}</p>

		<ul class="space-y-2">
			<li
				v-for="row in rows"
				:key="row.work_order"
				class="rounded-xl p-3"
				:style="{ background: 'var(--fm-canvas)' }"
			>
				<div class="flex flex-wrap items-baseline justify-between gap-2">
					<a
						class="fm-id text-sm font-semibold"
						:style="{ color: 'var(--fm-primary)' }"
						:href="`/app/work-order/${encodeURIComponent(row.work_order)}`"
						target="_blank"
						rel="noopener"
					>
						{{ row.work_order }}
					</a>
					<span class="text-xs fm-muted">{{ row.item_name }}</span>
				</div>

				<!-- Which ingredient, how short, and where it was looked for.
				     "This run is short" is not actionable; this is. -->
				<ul class="mt-1.5 space-y-0.5">
					<li
						v-for="item in row.items"
						:key="item.item_code"
						class="flex flex-wrap items-baseline gap-x-2 text-xs"
					>
						<span :style="{ color: 'var(--fm-ink)' }">{{ item.item_name }}</span>
						<span class="fm-num font-semibold" :style="{ color: 'var(--fm-bad)' }">
							short {{ fmt(item.short_qty) }} {{ item.uom }}
						</span>
						<span class="fm-muted">
							({{ fmt(item.available_qty) }} of {{ fmt(item.required_qty) }} in
							{{ item.warehouse }})
						</span>
					</li>
				</ul>
			</li>
		</ul>

		<p v-if="more > 0" class="mt-2 text-xs fm-muted">
			and {{ more }} more {{ more === 1 ? 'run' : 'runs' }} short of material.
		</p>
	</div>
</template>

<script setup>
const props = defineProps({
	rows: { type: Array, default: () => [] },
	more: { type: Number, default: 0 },
	label: { type: String, default: 'Short of material' },
})

const fmt = (value) =>
	Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })
</script>

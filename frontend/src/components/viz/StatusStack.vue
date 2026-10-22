<template>
	<figure class="fm-card p-4">
		<figcaption class="mb-2">
			<h3 class="text-sm font-semibold" :style="{ color: 'var(--viz-ink)' }">{{ title }}</h3>
			<p v-if="subtitle" class="text-xs" :style="{ color: 'var(--viz-ink-secondary)' }">{{ subtitle }}</p>
		</figcaption>

		<p v-if="!total" class="py-8 text-center text-sm text-gray-500">{{ emptyText }}</p>

		<template v-else>
			<!-- Part-to-whole as a single stacked bar. A 2px surface gap sits
			     between segments so adjacent fills never bleed together. -->
			<div class="flex h-7 w-full overflow-hidden rounded-md" role="img" :aria-label="ariaLabel">
				<div
					v-for="(row, index) in segments"
					:key="row.label"
					class="relative flex items-center justify-center"
					:style="{
						width: `${row.percent}%`,
						background: row.color,
						marginLeft: index ? '2px' : '0',
					}"
					:title="`${row.label}: ${row.value}`"
				>
					<!-- Direct value labels: the mandated relief for the two
					     status hues that sit below 3:1 on a white surface. -->
					<span
						v-if="row.percent >= 9"
						class="text-xs font-semibold"
						:style="{ color: row.labelInk }"
						style="font-variant-numeric: tabular-nums"
					>
						{{ row.value }}
					</span>
				</div>
			</div>

			<!-- Legend is always present, and each entry carries an icon plus a
			     word, so a status is never conveyed by colour alone. -->
			<ul class="mt-3 grid grid-cols-2 gap-y-1.5 text-xs sm:grid-cols-4">
				<li v-for="row in segments" :key="`k${row.label}`" class="flex items-center gap-1.5">
					<component :is="row.icon" class="h-3.5 w-3.5 shrink-0" :style="{ color: row.color }" aria-hidden="true" />
					<span :style="{ color: 'var(--viz-ink-secondary)' }">{{ row.label }}</span>
					<span class="font-semibold" :style="{ color: 'var(--viz-ink)' }">{{ row.value }}</span>
				</li>
			</ul>
		</template>
	</figure>
</template>

<script setup>
import { computed } from 'vue'
import { AlertTriangle, CheckCircle, XOctagon, PauseCircle } from 'lucide-vue-next'

const props = defineProps({
	title: { type: String, default: 'Stock by quality status' },
	subtitle: { type: String, default: '' },
	rows: { type: Array, default: () => [] },
	emptyText: { type: String, default: 'No quality-managed stock on hand.' },
})

/* Reserved status roles. Icon and ink are fixed per role so a colour never
   has to carry the meaning by itself. */
const ROLE = {
	good: { color: 'var(--viz-good)', icon: CheckCircle, labelInk: '#ffffff' },
	warning: { color: 'var(--viz-warning)', icon: AlertTriangle, labelInk: '#0b0b0b' },
	critical: { color: 'var(--viz-critical)', icon: XOctagon, labelInk: '#ffffff' },
	serious: { color: 'var(--viz-serious)', icon: PauseCircle, labelInk: '#0b0b0b' },
}

const total = computed(() => props.rows.reduce((sum, row) => sum + (Number(row.value) || 0), 0))

const segments = computed(() =>
	props.rows
		.filter((row) => Number(row.value) > 0)
		.map((row) => {
			const role = ROLE[row.role] || ROLE.warning
			return {
				label: row.label,
				value: Number(row.value),
				percent: total.value ? (Number(row.value) / total.value) * 100 : 0,
				...role,
			}
		})
)

const ariaLabel = computed(
	() =>
		`${props.title}: ` +
		segments.value.map((row) => `${row.label} ${row.value}`).join(', ')
)
</script>

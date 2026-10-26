<template>
	<figure :class="bare ? '' : 'fm-card p-4'">
		<figcaption class="mb-2">
			<h3 class="fm-viz-title">{{ title }}</h3>
			<p v-if="subtitle" class="fm-viz-subtitle">{{ subtitle }}</p>
		</figcaption>

		<p v-if="!total" class="fm-viz-empty">{{ emptyText }}</p>

		<template v-else>
			<!-- Part-to-whole as a single stacked bar. A 2px surface gap sits
			     between segments so adjacent fills never bleed together. -->
			<div class="relative" @pointerleave="active = null">
				<div class="flex h-8 w-full overflow-hidden rounded-lg" role="img" :aria-label="ariaLabel">
					<button
						v-for="(row, index) in segments"
						:key="row.label"
						type="button"
						class="relative flex items-center justify-center overflow-hidden transition-[filter] motion-reduce:transition-none"
						:style="{
							width: `${row.percent}%`,
							// A one-of-two-hundred segment is a third of a pixel
							// wide, which is no segment at all. The bar clips, so
							// the couple of pixels this borrows never spill.
							minWidth: '8px',
							background: row.color,
							marginLeft: index ? '2px' : '0',
							filter: active && active.label !== row.label ? 'saturate(0.45) opacity(0.65)' : 'none',
						}"
						:aria-label="`${row.label}: ${row.value} of ${total} batches`"
						@pointerenter="active = row"
						@focus="active = row"
						@blur="active = null"
					>
						<!-- Direct value labels: the mandated relief for the two
						     status hues that sit below 3:1 on a white surface.
						     Only where the number actually fits the segment.

						     The floor is 6%, not 9%: on a plant holding twelve
						     batches a single quarantined one is 8.3% of the bar -
						     some forty pixels, ample for one digit - and it was
						     going unlabelled, so the two statuses that most need
						     a number carried none. The segment clips its own
						     overflow, so a label that does not fit is cut rather
						     than pushed into its neighbour. -->
						<span
							v-if="row.percent >= 6"
							class="fm-num text-xs font-semibold"
							:style="{ color: row.labelInk }"
						>
							{{ row.value }}
						</span>
					</button>
				</div>

				<!-- A 3-of-63 segment is too thin to label, so hovering or
				     tabbing to it is how its number is read. -->
				<div
					v-if="active"
					class="pointer-events-none absolute -top-1 z-10 -translate-y-full rounded-lg px-2.5 py-1.5 text-xs shadow-lg"
					:style="tooltipStyle"
					role="status"
				>
					<span class="flex items-center gap-1.5 font-semibold">
						<component :is="active.icon" class="h-3.5 w-3.5" :style="{ color: active.color }" aria-hidden="true" />
						{{ active.label }}
					</span>
					<span class="fm-num block" :style="{ color: 'var(--fm-muted)' }">
						{{ active.value }} of {{ total }} batches · {{ Math.round(active.percent) }}%
					</span>
				</div>
			</div>

			<!-- Legend is always present, and each entry carries an icon plus a
			     word, so a status is never conveyed by colour alone. -->
			<!-- One row per status, count right-aligned: a 2x2 grid ran its
			     entries into one another at rail width, and the numbers never
			     lined up to be compared. -->
			<ul class="mt-3 space-y-1.5 text-sm">
				<li
					v-for="row in segments"
					:key="`k${row.label}`"
					class="flex items-center gap-2"
					@pointerenter="active = row"
					@pointerleave="active = null"
				>
					<component :is="row.icon" class="h-3.5 w-3.5 shrink-0" :style="{ color: row.color }" aria-hidden="true" />
					<span :style="{ color: 'var(--viz-ink)' }">{{ row.label }}</span>
					<span class="ml-auto fm-num font-semibold" :style="{ color: 'var(--viz-ink)' }">
						{{ row.value }}
					</span>
					<span class="w-14 text-right text-xs" :style="{ color: 'var(--viz-ink-secondary)' }">
						{{ row.value === 1 ? 'batch' : 'batches' }}
					</span>
				</li>
			</ul>
		</template>
	</figure>
</template>

<script setup>
import { computed, ref } from 'vue'
import { AlertTriangle, CheckCircle, XOctagon, PauseCircle } from 'lucide-vue-next'

const props = defineProps({
	title: { type: String, default: 'Stock by quality status' },
	subtitle: { type: String, default: '' },
	rows: { type: Array, default: () => [] },
	emptyText: { type: String, default: 'No quality-managed stock on hand.' },
	bare: Boolean,
})

/* Reserved status roles. Icon and ink are fixed per role so a colour never
   has to carry the meaning by itself. */
const ROLE = {
	good: { color: 'var(--viz-good)', icon: CheckCircle, labelInk: '#ffffff' },
	warning: { color: 'var(--viz-warning)', icon: AlertTriangle, labelInk: '#0b0b0b' },
	critical: { color: 'var(--viz-critical)', icon: XOctagon, labelInk: '#ffffff' },
	serious: { color: 'var(--viz-serious)', icon: PauseCircle, labelInk: '#0b0b0b' },
}

const active = ref(null)

const total = computed(() => props.rows.reduce((sum, row) => sum + (Number(row.value) || 0), 0))

const tooltipStyle = computed(() => {
	if (!active.value) return {}

	const index = segments.value.indexOf(active.value)
	const start = segments.value
		.slice(0, index)
		.reduce((sum, row) => sum + row.percent, 0)
	const middle = start + active.value.percent / 2

	// Anchored to whichever edge of its own segment keeps the box inside the
	// card: left-anchored past the halfway mark pushes it out of a narrow one.
	const edge =
		middle > 50
			? { right: `${Math.max(100 - start - active.value.percent, 0)}%` }
			: { left: `${start}%` }

	return {
		...edge,
		background: 'var(--fm-surface)',
		color: 'var(--fm-ink)',
		border: '1px solid var(--fm-border)',
	}
})

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

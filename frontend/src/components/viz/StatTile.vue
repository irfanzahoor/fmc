<template>
	<div class="fm-card p-4" :class="hero ? 'ring-1 ring-blue-200' : ''">
		<div class="flex items-start justify-between gap-2">
			<p class="fm-label">{{ label }}</p>
			<component
				v-if="icon"
				:is="icon"
				class="h-4 w-4 shrink-0"
				:style="{ color: 'var(--viz-muted)' }"
				aria-hidden="true"
			/>
		</div>

		<p class="mt-1 flex items-baseline gap-1" :class="hero ? 'text-fm-hero' : 'text-2xl'">
			<span class="font-semibold tracking-tight" :style="{ color: 'var(--viz-ink)' }">
				{{ display }}
			</span>
			<span
				v-if="unit && display !== emptyText"
				class="text-sm font-medium"
				:style="{ color: 'var(--viz-ink-secondary)' }"
			>{{ unit }}</span>
		</p>

		<!-- Status is never colour alone: the word is always present. -->
		<p v-if="note" class="mt-1 flex items-center gap-1 text-xs" :style="{ color: noteColor }">
			<component v-if="noteIcon" :is="noteIcon" class="h-3.5 w-3.5" aria-hidden="true" />
			<span>{{ note }}</span>
		</p>

		<p v-else-if="hint" class="mt-1 text-xs" :style="{ color: 'var(--viz-ink-secondary)' }">{{ hint }}</p>
	</div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
	label: { type: String, required: true },
	value: { type: [Number, String, null], default: null },
	unit: { type: String, default: '' },
	hint: { type: String, default: '' },
	note: { type: String, default: '' },
	// 'good' | 'warning' | 'serious' | 'critical' | '' — a reserved status role.
	noteRole: { type: String, default: '' },
	noteIcon: { type: [Object, Function], default: null },
	icon: { type: [Object, Function], default: null },
	hero: Boolean,
	decimals: { type: Number, default: 0 },
	emptyText: { type: String, default: '—' },
})

const display = computed(() => {
	if (props.value === null || props.value === undefined || props.value === '') {
		// Never show 0 for "we do not know" — that is a different fact.
		return props.emptyText
	}
	if (typeof props.value === 'number') {
		return props.value.toLocaleString(undefined, {
			minimumFractionDigits: props.decimals,
			maximumFractionDigits: props.decimals,
		})
	}
	return props.value
})

const noteColor = computed(() => {
	const map = {
		good: 'var(--viz-delta-up)',
		warning: 'var(--viz-ink-secondary)',
		serious: 'var(--viz-ink-secondary)',
		critical: 'var(--viz-critical)',
	}
	return map[props.noteRole] || 'var(--viz-ink-secondary)'
})
</script>

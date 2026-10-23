<template>
	<div class="fm-card p-4">
		<div class="flex items-start justify-between gap-2">
			<p class="text-sm font-semibold">{{ label }}</p>
			<span
				v-if="icon"
				class="grid h-8 w-8 shrink-0 place-items-center rounded-lg"
				:style="{ background: 'var(--fm-soft)', color: 'var(--fm-primary)' }"
				aria-hidden="true"
			>
				<component :is="icon" class="h-4 w-4" />
			</span>
		</div>

		<p class="fm-figure mt-2 flex items-baseline gap-1">
			<!-- Proportional, not tabular: these do not align in a column, and
			     zero-width digits make a figure like 121 read loose. -->
			<span class="text-[31px] font-extrabold leading-none">{{ display }}</span>
			<span v-if="unit && display !== emptyText" class="text-sm font-medium fm-muted">{{ unit }}</span>
		</p>

		<!-- The note always carries a word; the dot never states meaning alone. -->
		<p v-if="note" class="mt-2 flex items-center gap-1.5 text-xs">
			<span class="h-1.5 w-1.5 shrink-0 rounded-full" :style="{ background: dotColor }" aria-hidden="true" />
			<span :style="{ color: toneColor }">{{ note }}</span>
		</p>

		<!-- Trend last, per the stat-tile contract, so the label, figure and
		     note still line up across a row where only some cards carry one.
		     It has no axis and no values: it says "shape of the recent run",
		     and the chart below says the rest. -->
		<Sparkline v-if="trend.length > 1" class="mt-2.5" :values="trend" :label="`${label} trend`" />
	</div>
</template>

<script setup>
import { computed } from 'vue'

import Sparkline from '@/components/viz/Sparkline.vue'

const props = defineProps({
	label: { type: String, required: true },
	value: { type: [Number, String, null], default: null },
	unit: { type: String, default: '' },
	note: { type: String, default: '' },
	// 'good' | 'warn' | 'bad' | 'neutral'
	tone: { type: String, default: 'neutral' },
	icon: { type: [Object, Function], default: null },
	decimals: { type: Number, default: 0 },
	emptyText: { type: String, default: '—' },
	/** Plain numbers, oldest first; fewer than two draws nothing. */
	trend: { type: Array, default: () => [] },
})

const display = computed(() => {
	// A missing measurement is an em dash, never a zero: they mean
	// different things and a dashboard must not blur them.
	if (props.value === null || props.value === undefined || props.value === '') {
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

const TONES = {
	good: 'var(--fm-good)',
	warn: 'var(--fm-warn)',
	bad: 'var(--fm-bad)',
	neutral: 'var(--fm-muted)',
}

const toneColor = computed(() => TONES[props.tone] || TONES.neutral)
const dotColor = computed(() => TONES[props.tone] || TONES.neutral)
</script>

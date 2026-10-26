<template>
	<!-- role="img" with a sentence, because the ring is one fact and reading it
	     out arc by arc would say nothing. The figure is also drawn as text in
	     the middle, so the value never depends on seeing the arc at all. -->
	<figure
		class="relative shrink-0"
		:style="{ width: `${size}px`, height: `${size}px` }"
		role="img"
		:aria-label="`${rounded}% complete — ${label}`"
	>
		<svg :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`" aria-hidden="true">
			<circle
				:cx="centre"
				:cy="centre"
				:r="radius"
				fill="none"
				:stroke-width="stroke"
				:stroke="track"
			/>
			<!-- A cap at zero: with no arc to see, the ring otherwise reads as a
			     disabled control rather than as a run that has not started. -->
			<circle
				v-if="rounded === 0"
				:cx="centre"
				:cy="stroke / 2"
				:r="stroke / 2"
				:fill="colour"
				opacity="0.35"
			/>
			<circle
				:cx="centre"
				:cy="centre"
				:r="radius"
				fill="none"
				:stroke-width="stroke"
				:stroke="colour"
				stroke-linecap="round"
				:stroke-dasharray="circumference"
				:stroke-dashoffset="offset"
				:transform="`rotate(-90 ${centre} ${centre})`"
				class="fm-ring-arc"
			/>
		</svg>

		<figcaption
			class="absolute inset-0 grid place-items-center text-center leading-none"
			aria-hidden="true"
		>
			<span>
				<span class="fm-num block text-xl font-extrabold leading-none">
					{{ rounded }}<span class="text-sm font-bold">%</span>
				</span>
				<span class="mt-1 block text-[9px] font-semibold uppercase tracking-[0.1em] fm-muted">done</span>
			</span>
		</figcaption>
	</figure>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
	/** 0-100. Anything outside is clamped rather than drawn off the circle. */
	value: { type: Number, default: 0 },
	size: { type: Number, default: 88 },
	stroke: { type: Number, default: 8 },
	/** What the ring is a percentage *of*, for the screen-reader sentence. */
	label: { type: String, default: 'complete' },
	/** Chrome tokens, not chart tokens: this is a control's state, like the
	    progress bar on the queue cards, and re-tints with the theme as they do. */
	colour: { type: String, default: 'var(--fm-primary)' },
	track: { type: String, default: 'var(--fm-border)' },
})

const rounded = computed(() => Math.round(Math.min(100, Math.max(0, Number(props.value) || 0))))
const centre = computed(() => props.size / 2)
const radius = computed(() => centre.value - props.stroke / 2)
const circumference = computed(() => 2 * Math.PI * radius.value)
const offset = computed(() => circumference.value * (1 - rounded.value / 100))
</script>

<style scoped>
/* The arc grows into place on open. Reduced motion is honoured globally in
   index.css, which zeroes the duration rather than removing the final state. */
.fm-ring-arc {
	transition: stroke-dashoffset 520ms cubic-bezier(0.22, 1, 0.36, 1);
}
</style>

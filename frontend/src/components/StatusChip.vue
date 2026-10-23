<template>
	<span class="fm-chip" :class="chipClass">
		<component :is="icon" class="h-3.5 w-3.5" aria-hidden="true" />
		{{ label }}
	</span>
</template>

<script setup>
import { computed } from 'vue'
import { AlertTriangle, CheckCircle, HelpCircle, PauseCircle, XOctagon } from 'lucide-vue-next'

const props = defineProps({
	status: { type: String, default: '' },
})

/* One fixed meaning per status, in every theme. Icon and word always travel
   with the colour, so the state reads without hue. */
const MAP = {
	Released: { cls: 'fm-chip-good', icon: CheckCircle },
	Quarantine: { cls: 'fm-chip-warn', icon: AlertTriangle },
	Hold: { cls: 'fm-chip-warn', icon: PauseCircle },
	Rejected: { cls: 'fm-chip-bad', icon: XOctagon },
}

const entry = computed(() => MAP[props.status] || { cls: 'fm-chip-soft', icon: HelpCircle })
const chipClass = computed(() => entry.value.cls)
const icon = computed(() => entry.value.icon)
const label = computed(() => props.status || 'Not managed')
</script>

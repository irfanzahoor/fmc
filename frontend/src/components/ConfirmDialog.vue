<template>
	<Teleport to="body">
		<!-- Teleported out of the app root for stacking, so it has to carry the
		     theme with it: every token in this app is scoped under `.fm-app`,
		     and without these attributes the dialog renders unstyled. -->
		<div
			v-if="open"
			class="fm-app fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center"
			style="background: rgb(10 20 16 / 0.45); min-height: 0"
			:data-theme="appearance.theme"
			:data-font="appearance.font"
			role="presentation"
			@click.self="cancel"
		>
			<div
				ref="panel"
				class="fm-card w-full max-w-md p-5"
				role="alertdialog"
				aria-modal="true"
				:aria-labelledby="titleId"
				:aria-describedby="bodyId"
				@keydown.esc="cancel"
				@keydown.tab="trapFocus"
			>
				<h2 :id="titleId" class="text-lg font-bold">{{ title }}</h2>
				<p :id="bodyId" class="mt-1.5 text-sm fm-muted">{{ body }}</p>

				<!-- What is about to be posted, in the words of the record. A
				     confirmation that only says "are you sure" adds a click
				     without adding certainty. -->
				<dl v-if="details.length" class="mt-3 space-y-1 rounded-xl p-3 text-sm" :style="{ background: 'var(--fm-canvas)' }">
					<div v-for="row in details" :key="row.label" class="flex items-baseline justify-between gap-3">
						<dt class="fm-muted">{{ row.label }}</dt>
						<dd class="fm-num font-semibold">{{ row.value }}</dd>
					</div>
				</dl>

				<div class="mt-5 flex flex-wrap justify-end gap-2">
					<button ref="cancelButton" type="button" class="fm-btn-ghost fm-tap px-4 text-sm" @click="cancel">
						{{ cancelLabel }}
					</button>
					<button
						type="button"
						class="fm-tap flex items-center gap-2 px-4 text-sm"
						:class="destructive ? 'fm-btn-danger' : 'fm-btn-primary'"
						@click="confirm"
					>
						{{ confirmLabel }}
					</button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { nextTick, ref, useId, watch } from 'vue'

import { appearance } from '@/data/appearance'

const props = defineProps({
	open: Boolean,
	title: { type: String, required: true },
	body: { type: String, default: '' },
	details: { type: Array, default: () => [] },
	confirmLabel: { type: String, default: 'Confirm' },
	cancelLabel: { type: String, default: 'Cancel' },
	destructive: Boolean,
})

const emit = defineEmits(['confirm', 'cancel'])

const titleId = useId()
const bodyId = useId()
const panel = ref(null)
const cancelButton = ref(null)

/* Focus lands on Cancel, not Confirm: a dialog that opens with the destructive
   action focused turns a stray Enter into a posting. */
watch(
	() => props.open,
	async (isOpen) => {
		if (!isOpen) return
		await nextTick()
		cancelButton.value?.focus()
	},
)

function confirm() {
	emit('confirm')
}

function cancel() {
	emit('cancel')
}

/** Keep Tab inside the dialog while it is open. */
function trapFocus(event) {
	const focusable = panel.value?.querySelectorAll('button, [href], input, select, textarea')
	if (!focusable?.length) return

	const first = focusable[0]
	const last = focusable[focusable.length - 1]

	if (event.shiftKey && document.activeElement === first) {
		event.preventDefault()
		last.focus()
	} else if (!event.shiftKey && document.activeElement === last) {
		event.preventDefault()
		first.focus()
	}
}
</script>

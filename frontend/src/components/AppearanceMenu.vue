<template>
	<div class="relative">
		<button
			ref="trigger"
			type="button"
			class="fm-btn-ghost fm-tap flex items-center gap-2 px-3 text-sm"
			:aria-expanded="open"
			aria-haspopup="dialog"
			@click="open = !open"
		>
			<Palette class="h-4 w-4" aria-hidden="true" />
			<span class="hidden sm:inline">Appearance</span>
		</button>

		<div
			v-if="open"
			ref="panel"
			class="fm-card absolute right-0 z-40 mt-2 w-64 p-3"
			role="dialog"
			aria-label="Appearance"
		>
			<p class="fm-label mb-2">Theme</p>
			<ul class="space-y-1">
				<li v-for="option in THEMES" :key="option.value">
					<button
						type="button"
						class="fm-tap flex w-full items-center gap-2.5 rounded-lg px-2 text-left text-sm"
						:style="appearance.theme === option.value ? { background: 'var(--fm-soft)' } : {}"
						@click="appearance.setTheme(option.value)"
					>
						<span
							class="h-4 w-4 shrink-0 rounded-full border"
							:style="{ background: option.swatch, borderColor: option.accent }"
							aria-hidden="true"
						/>
						<span class="flex-1">{{ option.label }}</span>
						<Check
							v-if="appearance.theme === option.value"
							class="h-4 w-4"
							:style="{ color: 'var(--fm-primary)' }"
							aria-hidden="true"
						/>
					</button>
				</li>
			</ul>

			<p class="fm-label mb-2 mt-3">Typography</p>
			<ul class="space-y-1">
				<li v-for="option in FONTS" :key="option.value">
					<button
						type="button"
						class="fm-tap flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left"
						:style="appearance.font === option.value ? { background: 'var(--fm-soft)' } : {}"
						@click="appearance.setFont(option.value)"
					>
						<span class="flex-1">
							<span class="block text-sm">{{ option.label }}</span>
							<span class="block text-xs fm-muted">{{ option.hint }}</span>
						</span>
						<Check
							v-if="appearance.font === option.value"
							class="mt-0.5 h-4 w-4 shrink-0"
							:style="{ color: 'var(--fm-primary)' }"
							aria-hidden="true"
						/>
					</button>
				</li>
			</ul>
		</div>
	</div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { Check, Palette } from 'lucide-vue-next'

import { FONTS, THEMES, appearance } from '@/data/appearance'

const open = ref(false)
const trigger = ref(null)
const panel = ref(null)

function onPointerDown(event) {
	if (!open.value) return
	if (trigger.value?.contains(event.target) || panel.value?.contains(event.target)) return
	open.value = false
}

function onKeydown(event) {
	if (event.key === 'Escape' && open.value) {
		open.value = false
		trigger.value?.focus()
	}
}

onMounted(() => {
	document.addEventListener('pointerdown', onPointerDown)
	document.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
	document.removeEventListener('pointerdown', onPointerDown)
	document.removeEventListener('keydown', onKeydown)
})
</script>

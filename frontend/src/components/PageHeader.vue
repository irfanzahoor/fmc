<template>
	<header class="mb-5">
		<p v-if="eyebrow" class="fm-eyebrow mb-1.5">{{ eyebrow }}</p>

		<div class="flex flex-wrap items-start justify-between gap-3">
			<div class="min-w-0">
				<h1 class="text-[25px] font-extrabold leading-tight lg:text-[31px]">{{ title }}</h1>
				<p v-if="subtitle" class="mt-1 text-sm fm-muted">{{ subtitle }}</p>
			</div>

			<div v-if="$slots.actions" class="flex flex-wrap items-center gap-2">
				<slot name="actions" />
			</div>
		</div>

		<!-- Workspace / Insights tabs, where a page has both. -->
		<nav v-if="tabs.length" class="mt-4 flex gap-1 border-b" :style="{ borderColor: 'var(--fm-border)' }" aria-label="Views">
			<RouterLink
				v-for="tab in tabs"
				:key="tab.name"
				:to="{ name: tab.name }"
				class="fm-tap -mb-px flex items-center gap-2 border-b-2 px-3 text-sm font-semibold"
				:style="
					route.name === tab.name
						? { borderColor: 'var(--fm-primary)', color: 'var(--fm-primary)' }
						: { borderColor: 'transparent', color: 'var(--fm-muted)' }
				"
				:aria-current="route.name === tab.name ? 'page' : undefined"
			>
				<component :is="tab.icon" class="h-4 w-4" aria-hidden="true" />
				{{ tab.label }}
			</RouterLink>
		</nav>
	</header>
</template>

<script setup>
import { useRoute } from 'vue-router'

defineProps({
	eyebrow: { type: String, default: '' },
	title: { type: String, required: true },
	subtitle: { type: String, default: '' },
	tabs: { type: Array, default: () => [] },
})

const route = useRoute()
</script>

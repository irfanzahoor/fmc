<template>
	<component
		:is="href ? 'a' : 'div'"
		:href="href"
		:target="href ? '_blank' : null"
		:rel="href ? 'noopener' : null"
		class="fm-card block p-4 transition-shadow motion-reduce:transition-none"
		:class="href ? 'hover:shadow-md focus-visible:shadow-md' : ''"
	>
		<p class="text-sm font-semibold">{{ metric.label }}</p>

		<p class="fm-figure mt-2 flex items-baseline gap-1">
			<span
				v-if="metric.currency && currency && display !== EMPTY"
				class="text-sm font-medium fm-muted"
			>{{ currency }}</span>
			<span class="text-[28px] font-extrabold leading-none">{{ display }}</span>
			<span v-if="metric.unit && display !== EMPTY" class="text-sm font-medium fm-muted">
				{{ metric.unit }}
			</span>
		</p>

		<p v-if="href" class="mt-2 flex items-center gap-1 text-xs" :style="{ color: 'var(--fm-primary)' }">
			<ExternalLink class="h-3 w-3 shrink-0" aria-hidden="true" />
			<span>{{ metric.link.doctype }}</span>
		</p>
		<!-- No link is not a failure: the figure is simply one this account
		     cannot open the records behind. Saying nothing is better than an
		     affordance that refuses on click. -->
	</component>
</template>

<script setup>
import { computed } from 'vue'
import { ExternalLink } from 'lucide-vue-next'

const EMPTY = '—'

const props = defineProps({
	metric: { type: Object, required: true },
	// A cost figure without its currency is ambiguous on a multi-company site.
	currency: { type: String, default: '' },
})

const display = computed(() => {
	const value = props.metric.value
	// A missing measurement is an em dash, never a zero.
	if (value === null || value === undefined || value === '') return EMPTY

	if (typeof value === 'number') {
		return value.toLocaleString(undefined, {
			minimumFractionDigits: props.metric.decimals || 0,
			maximumFractionDigits: props.metric.decimals || 0,
		})
	}
	return value
})

/** A Desk list filtered to exactly the rows behind this figure. */
const href = computed(() => {
	const link = props.metric.link
	if (!link) return null

	const slug = link.doctype.toLowerCase().replaceAll(' ', '-')
	const query = new URLSearchParams()
	for (const [field, value] of Object.entries(link.filters || {})) {
		query.append(field, Array.isArray(value) ? JSON.stringify(value) : value)
	}

	return `/app/${slug}?${query.toString()}`
})
</script>

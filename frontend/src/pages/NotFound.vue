<template>
	<div class="space-y-4">
		<PageHeader eyebrow="Workspace" title="Page not found" subtitle="That address is not part of the console." />

		<div class="fm-card p-8 text-center">
			<Compass class="mx-auto h-7 w-7 text-gray-400" aria-hidden="true" />
			<p class="mt-2 text-sm font-medium text-gray-900">
				Nothing lives at <span class="fm-id">{{ route.fullPath }}</span>
			</p>
			<p class="mt-1 text-sm text-gray-600">The link may be out of date, or the address mistyped.</p>
			<RouterLink
				:to="{ name: 'Dashboard' }"
				class="fm-btn-primary fm-tap mt-4 inline-flex items-center gap-2 px-4 text-sm"
			>
				Go to the overview
			</RouterLink>
		</div>
	</div>
</template>

<script setup>
import { Compass } from 'lucide-vue-next'
import { RouterLink, useRoute } from 'vue-router'

import PageHeader from '@/components/PageHeader.vue'

const route = useRoute()
</script>

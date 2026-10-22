<template>
	<div v-if="loading" class="fm-card flex items-center justify-center gap-3 p-8 text-sm text-gray-600">
		<Spinner class="h-4 w-4" />
		<span>{{ loadingText }}</span>
	</div>

	<p v-else-if="error" role="alert" class="fm-card border-red-200 bg-red-50 p-4 text-sm text-red-800">
		<span class="font-medium">Could not load.</span>
		<span class="mt-1 block whitespace-pre-line">{{ errorMessage(error) }}</span>
		<Button v-if="onRetry" class="mt-3" @click="onRetry">Try again</Button>
	</p>

	<div v-else-if="empty" class="fm-card p-8 text-center">
		<component :is="icon" v-if="icon" class="mx-auto h-7 w-7 text-gray-400" aria-hidden="true" />
		<p class="mt-2 text-sm font-medium text-gray-900">{{ emptyTitle }}</p>
		<p v-if="emptyHint" class="mt-1 text-sm text-gray-600">{{ emptyHint }}</p>
	</div>

	<slot v-else />
</template>

<script setup>
import { errorMessage } from '@/data/api'

defineProps({
	loading: Boolean,
	error: { type: [Object, String, Error], default: null },
	empty: Boolean,
	loadingText: { type: String, default: 'Loading…' },
	emptyTitle: { type: String, default: 'Nothing here' },
	emptyHint: { type: String, default: '' },
	icon: { type: [Object, Function], default: null },
	onRetry: { type: Function, default: null },
})
</script>

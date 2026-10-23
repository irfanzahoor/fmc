<template>
	<div v-if="loading" class="fm-card flex items-center justify-center gap-3 p-8 text-sm text-gray-600">
		<Spinner class="h-4 w-4" />
		<span>{{ loadingText }}</span>
	</div>

	<!--
		The tint comes from the theme tokens, not Tailwind: `.fm-app .fm-card`
		is more specific than `.bg-red-50`, so a utility class here renders as
		a plain white card.
	-->
	<div
		v-else-if="error"
		role="alert"
		class="fm-card p-4 text-sm"
		:style="{ background: 'var(--fm-bad-bg)', borderColor: 'var(--fm-bad)', color: 'var(--fm-bad)' }"
	>
		<template v-if="missingRoles">
			<p class="flex items-center gap-2 font-medium">
				<Lock class="h-4 w-4 shrink-0" aria-hidden="true" />
				<span>You do not have access to this screen.</span>
			</p>
			<p class="mt-1">
				It reads standard ERPNext documents, so it needs the
				<span class="font-medium">{{ missingRoles }}</span>
				{{ requiredRoles.length === 1 ? 'role' : 'roles' }}. Ask an administrator to add
				{{ requiredRoles.length === 1 ? 'it' : 'them' }} to your account.
			</p>
			<p class="mt-2 text-xs opacity-80">{{ errorMessage(error) }}</p>
		</template>

		<template v-else>
			<p class="font-medium">Could not load.</p>
			<p class="mt-1 whitespace-pre-line">{{ errorMessage(error) }}</p>
		</template>

		<Button v-if="onRetry && !missingRoles" class="mt-3" @click="onRetry">Try again</Button>
	</div>

	<div v-else-if="empty" class="fm-card p-8 text-center">
		<component :is="icon" v-if="icon" class="mx-auto h-7 w-7 text-gray-400" aria-hidden="true" />
		<p class="mt-2 text-sm font-medium text-gray-900">{{ emptyTitle }}</p>
		<p v-if="emptyHint" class="mt-1 text-sm text-gray-600">{{ emptyHint }}</p>
	</div>

	<slot v-else />
</template>

<script setup>
import { computed } from 'vue'
import { Lock } from 'lucide-vue-next'

import { errorMessage, isPermissionError } from '@/data/api'

const props = defineProps({
	loading: Boolean,
	error: { type: [Object, String, Error], default: null },
	empty: Boolean,
	loadingText: { type: String, default: 'Loading…' },
	emptyTitle: { type: String, default: 'Nothing here' },
	emptyHint: { type: String, default: '' },
	icon: { type: [Object, Function], default: null },
	onRetry: { type: Function, default: null },
	// The ERPNext roles this screen reads through, so a refusal can name them
	// instead of repeating the server's sentence about one DocType.
	requiredRoles: { type: Array, default: () => [] },
})

const missingRoles = computed(() => {
	if (!props.requiredRoles.length || !isPermissionError(props.error)) return null
	return props.requiredRoles.join(', ')
})
</script>

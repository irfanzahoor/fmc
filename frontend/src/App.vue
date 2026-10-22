<template>
	<div class="fm-app">
		<a href="#fm-main" class="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:shadow">
			Skip to content
		</a>

		<header class="sticky top-0 z-20 border-b border-gray-200 bg-white/95 backdrop-blur">
			<div class="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3">
				<span
					class="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-white"
					style="background: linear-gradient(135deg, #2a78d6, #1c5cab)"
					aria-hidden="true"
				>
					<Factory class="h-4.5 w-4.5" />
				</span>
				<div class="min-w-0">
					<h1 class="truncate text-base font-semibold leading-tight tracking-tight">
						Food Manufacturing
					</h1>
					<p class="truncate text-xs text-gray-500">Spice &amp; masala operations</p>
				</div>

				<label class="ml-auto flex items-center gap-2 text-sm">
					<span class="fm-label hidden sm:inline">Company</span>
					<select
						v-model="company"
						class="fm-tap rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-sm font-medium"
						:disabled="session.loading || !session.companies.length"
						aria-label="Company"
					>
						<option v-for="name in session.companies" :key="name" :value="name">
							{{ name }}
						</option>
					</select>
				</label>
			</div>

			<nav aria-label="Sections" class="mx-auto max-w-7xl overflow-x-auto px-2">
				<ul class="flex min-w-max gap-1 pb-2">
					<li v-for="item in navigation" :key="item.name">
						<RouterLink
							:to="{ name: item.name }"
							class="fm-tap flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors motion-reduce:transition-none"
							:class="
								route.name === item.name
									? 'bg-gray-900 text-white'
									: 'text-gray-700 hover:bg-gray-100'
							"
							:aria-current="route.name === item.name ? 'page' : undefined"
						>
							<component :is="item.icon" class="h-4 w-4" aria-hidden="true" />
							{{ item.label }}
							<!-- A count, not a colour: it reads with hue removed. -->
							<span
								v-if="item.count"
								class="rounded-full px-1.5 text-xs font-semibold"
								:class="route.name === item.name ? 'bg-white/20 text-white' : 'bg-gray-200 text-gray-800'"
							>
								{{ item.count }}
							</span>
						</RouterLink>
					</li>
				</ul>
			</nav>
		</header>

		<main id="fm-main" class="mx-auto max-w-7xl px-4 py-5">
			<p v-if="session.error" role="alert" class="fm-card mb-4 border-red-200 bg-red-50 p-3 text-sm text-red-800">
				{{ errorMessage(session.error) }}
			</p>

			<RouterView v-if="session.company" :company="session.company" :key="session.company" />

			<p v-else-if="!session.loading" class="fm-card p-6 text-center text-sm text-gray-600">
				No company is available to you. Ask an administrator for access.
			</p>
		</main>
	</div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ClipboardCheck, Factory, LayoutDashboard, PackageCheck, Truck } from 'lucide-vue-next'

import { errorMessage, quality } from '@/data/api'
import { session } from '@/data/session'

const route = useRoute()
const pendingQc = ref(0)

const company = computed({
	get: () => session.company,
	set: (value) => session.setCompany(value),
})

const navigation = computed(() => [
	{ name: 'Dashboard', label: 'Overview', icon: LayoutDashboard },
	{ name: 'Production', label: 'Production', icon: Factory },
	{ name: 'Quality', label: 'Quality', icon: ClipboardCheck, count: pendingQc.value },
	{ name: 'Receiving', label: 'Receiving', icon: PackageCheck },
	{ name: 'Dispatch', label: 'Dispatch', icon: Truck },
])

async function loadCounts() {
	if (!session.company) return
	try {
		const counts = await quality.counts({ company: session.company })
		pendingQc.value = counts.total
	} catch (error) {
		// A failed badge must not break the shell.
		pendingQc.value = 0
	}
}

onMounted(async () => {
	await session.load()
	await loadCounts()
})

watch(() => session.company, loadCounts)
</script>

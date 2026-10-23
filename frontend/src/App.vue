<template>
	<div class="fm-app lg:flex" :data-theme="appearance.theme" :data-font="appearance.font">
		<a href="#fm-main" class="fm-skip sr-only focus:not-sr-only">Skip to content</a>

		<!-- Desktop sidebar: 240px, dark, with the workspace/insights split. -->
		<aside
			class="hidden w-60 shrink-0 flex-col lg:flex"
			:style="{ background: 'var(--fm-sidebar)' }"
		>
			<div class="flex items-center gap-3 px-5 py-5">
				<span
					class="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-sm font-bold"
					style="background: #ffffff; color: var(--fm-sidebar)"
					aria-hidden="true"
				>
					FMC
				</span>
				<span class="min-w-0">
					<span class="block text-lg font-bold leading-tight text-white">FMC</span>
					<span class="block text-xs leading-tight" :style="{ color: 'var(--fm-side-ink)' }">
						Food manufacturing, connected.
					</span>
				</span>
			</div>

			<nav class="flex-1 overflow-y-auto px-3 pb-4" aria-label="Sections">
				<template v-for="group in navigation" :key="group.label">
					<p
						class="px-2 pb-1.5 pt-4 text-[11px] font-bold uppercase tracking-[0.12em]"
						:style="{ color: 'var(--fm-side-ink)', opacity: 0.75 }"
					>
						{{ group.label }}
					</p>
					<ul class="space-y-0.5">
						<li v-for="item in group.items" :key="item.name">
							<RouterLink
								:to="{ name: item.name }"
								class="fm-tap flex items-center gap-3 rounded-xl px-3 text-sm font-medium transition-colors motion-reduce:transition-none"
								:style="linkStyle(item.name)"
								:aria-current="isActive(item.name) ? 'page' : undefined"
							>
								<component :is="item.icon" class="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
								<span class="flex-1">{{ item.label }}</span>
								<span
									v-if="item.count"
									class="fm-num rounded-full px-1.5 py-0.5 text-[11px] font-bold"
									style="background: rgba(255, 255, 255, 0.16); color: #fff"
								>
									{{ item.count }}
								</span>
							</RouterLink>
						</li>
					</ul>
				</template>
			</nav>

			<div class="mt-auto border-t px-5 py-4" style="border-color: rgba(255, 255, 255, 0.1)">
				<p class="truncate text-sm font-semibold text-white">{{ session.company || '—' }}</p>
				<p class="truncate text-xs" :style="{ color: 'var(--fm-side-ink)' }">
					Spice &amp; masala operations
				</p>
			</div>
		</aside>

		<div class="flex min-w-0 flex-1 flex-col">
			<!-- Topbar -->
			<header
				class="sticky top-0 z-30 border-b"
				:style="{ background: 'var(--fm-surface)', borderColor: 'var(--fm-border)' }"
			>
				<div class="flex items-center gap-3 px-4 py-3 lg:px-7">
					<span class="flex items-center gap-2 text-sm lg:hidden">
						<span
							class="grid h-8 w-8 place-items-center rounded-lg text-[11px] font-bold text-white"
							:style="{ background: 'var(--fm-sidebar)' }"
							aria-hidden="true"
						>
							FMC
						</span>
					</span>

					<nav class="hidden items-center gap-2 text-sm lg:flex" aria-label="Breadcrumb">
						<span class="fm-muted">Workspace</span>
						<ChevronRight class="h-4 w-4 fm-muted" aria-hidden="true" />
						<span class="font-semibold">{{ currentLabel }}</span>
					</nav>

					<div class="ml-auto flex items-center gap-2">
						<label class="flex items-center gap-2">
							<span class="sr-only">Company</span>
							<span class="fm-btn-ghost fm-tap flex items-center gap-2 px-2.5">
								<Building2 class="h-4 w-4 shrink-0 fm-muted" aria-hidden="true" />
								<select
									v-model="company"
									class="max-w-[9rem] bg-transparent text-sm font-medium outline-none sm:max-w-none"
									:disabled="session.loading || !session.companies.length"
								>
									<option v-for="name in session.companies" :key="name" :value="name">
										{{ name }}
									</option>
								</select>
							</span>
						</label>

						<AppearanceMenu />
					</div>
				</div>
			</header>

			<main id="fm-main" class="flex-1 px-4 py-5 pb-24 lg:px-7 lg:pb-8">
				<p
					v-if="session.error"
					role="alert"
					class="fm-card mb-4 p-3 text-sm"
					:style="{ borderColor: 'var(--fm-bad)', color: 'var(--fm-bad)' }"
				>
					{{ errorMessage(session.error) }}
				</p>

				<RouterView
					v-if="session.company"
					:company="session.company"
					:key="session.company"
					@counts-changed="loadCounts"
				/>

				<p v-else-if="!session.loading" class="fm-card p-6 text-center text-sm fm-muted">
					No company is available to you. Ask an administrator for access.
				</p>
			</main>
		</div>

		<!-- Phone navigation: all six operational pages stay reachable. -->
		<nav
			class="fixed inset-x-0 bottom-0 z-30 border-t lg:hidden"
			:style="{ background: 'var(--fm-sidebar)', borderColor: 'rgba(255,255,255,0.08)' }"
			aria-label="Sections"
		>
			<ul class="flex">
				<li v-for="item in phoneNavigation" :key="item.name" class="flex-1">
					<RouterLink
						:to="{ name: item.name }"
						class="fm-tap relative flex flex-col items-center justify-center gap-0.5 py-1.5 text-[10px] font-medium"
						:style="{
							color: isActive(item.name) ? '#fff' : 'var(--fm-side-ink)',
						}"
						:aria-current="isActive(item.name) ? 'page' : undefined"
					>
						<component :is="item.icon" class="h-5 w-5" aria-hidden="true" />
						<span>{{ item.short }}</span>
						<span
							v-if="item.count"
							class="fm-num absolute right-1/4 top-0.5 rounded-full px-1 text-[9px] font-bold text-white"
							:style="{ background: 'var(--fm-primary)' }"
						>
							{{ item.count }}
						</span>
					</RouterLink>
				</li>
			</ul>
		</nav>
	</div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
	Building2,
	ChevronRight,
	ClipboardCheck,
	Factory,
	LayoutDashboard,
	LineChart,
	PackageCheck,
	ShieldCheck,
	Siren,
	Truck,
} from 'lucide-vue-next'

import AppearanceMenu from '@/components/AppearanceMenu.vue'
import { errorMessage, quality } from '@/data/api'
import { appearance } from '@/data/appearance'
import { session } from '@/data/session'

const route = useRoute()
const pendingQc = ref(0)

const company = computed({
	get: () => session.company,
	set: (value) => session.setCompany(value),
})

const navigation = computed(() => [
	{
		label: 'Workspace',
		items: [
			{ name: 'Dashboard', label: 'Overview', icon: LayoutDashboard },
			{ name: 'Production', label: 'Production', icon: Factory },
			{ name: 'Quality', label: 'Quality', icon: ShieldCheck, count: pendingQc.value },
			{ name: 'Receiving', label: 'Receiving', icon: PackageCheck },
			{ name: 'Dispatch', label: 'Dispatch', icon: Truck },
			{ name: 'Recall', label: 'Recall', icon: Siren },
		],
	},
	{
		label: 'Insights',
		items: [
			{ name: 'ProductionInsights', label: 'Production insights', icon: LineChart },
			{ name: 'QualityInsights', label: 'Quality overview', icon: ClipboardCheck },
		],
	},
])

const phoneNavigation = computed(() => [
	{ name: 'Dashboard', short: 'Overview', icon: LayoutDashboard },
	{ name: 'Production', short: 'Produce', icon: Factory },
	{ name: 'Quality', short: 'Quality', icon: ShieldCheck, count: pendingQc.value },
	{ name: 'Receiving', short: 'Goods in', icon: PackageCheck },
	{ name: 'Dispatch', short: 'Dispatch', icon: Truck },
	{ name: 'Recall', short: 'Recall', icon: Siren },
])

const allItems = computed(() => navigation.value.flatMap((group) => group.items))
const currentLabel = computed(
	() => allItems.value.find((item) => item.name === route.name)?.label || 'Workspace'
)

function isActive(name) {
	return route.name === name
}

function linkStyle(name) {
	return isActive(name)
		? { background: 'var(--fm-primary)', color: '#fff' }
		: { color: 'var(--fm-side-ink)' }
}

async function loadCounts() {
	if (!session.company) return
	try {
		const counts = await quality.counts({ company: session.company })
		pendingQc.value = counts.total
	} catch {
		// A failed badge must never break the shell.
		pendingQc.value = 0
	}
}

onMounted(async () => {
	await session.load()
	await loadCounts()
})

watch(() => session.company, loadCounts)
</script>

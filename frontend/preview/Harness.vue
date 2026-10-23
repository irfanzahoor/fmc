<template>
	<!-- Design harness: the real shell and page components against fixture data,
	     so the UI can be opened and screenshotted without a Frappe session. -->
	<div class="fm-app lg:flex" :data-theme="theme" :data-font="font">
		<aside class="hidden w-60 shrink-0 flex-col lg:flex" :style="{ background: 'var(--fm-sidebar)' }">
			<div class="flex items-center gap-3 px-5 py-5">
				<span class="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-sm font-bold"
					style="background:#fff;color:var(--fm-sidebar)">FMC</span>
				<span class="min-w-0">
					<span class="block text-lg font-bold leading-tight text-white">FMC</span>
					<span class="block text-xs leading-tight" :style="{ color: 'var(--fm-side-ink)' }">
						Food manufacturing, connected.
					</span>
				</span>
			</div>
			<nav class="flex-1 px-3 pb-4">
				<template v-for="group in nav" :key="group.label">
					<p class="px-2 pb-1.5 pt-4 text-[11px] font-bold uppercase tracking-[0.12em]"
						:style="{ color: 'var(--fm-side-ink)', opacity: 0.75 }">{{ group.label }}</p>
					<ul class="space-y-0.5">
						<li v-for="item in group.items" :key="item.label">
							<span class="fm-tap flex items-center gap-3 rounded-xl px-3 text-sm font-medium"
								:style="item.active
									? { background: 'var(--fm-primary)', color: '#fff' }
									: { color: 'var(--fm-side-ink)' }">
								<component :is="item.icon" class="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
								<span class="flex-1">{{ item.label }}</span>
								<span v-if="item.count" class="fm-num rounded-full px-1.5 py-0.5 text-[11px] font-bold"
									style="background:rgba(255,255,255,.16);color:#fff">{{ item.count }}</span>
							</span>
						</li>
					</ul>
				</template>
			</nav>
			<div class="mt-auto border-t px-5 py-4" style="border-color:rgba(255,255,255,.1)">
				<p class="truncate text-sm font-semibold text-white">{{ data.company }}</p>
				<p class="truncate text-xs" :style="{ color: 'var(--fm-side-ink)' }">Spice &amp; masala operations</p>
			</div>
		</aside>

		<div class="flex min-w-0 flex-1 flex-col">
			<header class="sticky top-0 z-30 border-b"
				:style="{ background: 'var(--fm-surface)', borderColor: 'var(--fm-border)' }">
				<div class="flex items-center gap-3 px-4 py-3 lg:px-7">
					<nav class="hidden items-center gap-2 text-sm lg:flex">
						<span class="fm-muted">Workspace</span>
						<ChevronRight class="h-4 w-4 fm-muted" aria-hidden="true" />
						<span class="font-semibold">Overview</span>
					</nav>
					<div class="ml-auto flex items-center gap-2">
						<span class="fm-btn-ghost fm-tap flex items-center gap-2 px-2.5">
							<Building2 class="h-4 w-4 shrink-0 fm-muted" aria-hidden="true" />
							<span class="text-sm font-medium">{{ data.company }}</span>
						</span>
						<span class="fm-btn-ghost fm-tap flex items-center gap-2 px-3 text-sm">
							<Palette class="h-4 w-4" aria-hidden="true" />
							<span class="hidden sm:inline">Appearance</span>
						</span>
					</div>
				</div>
			</header>

			<main class="flex-1 px-4 py-5 pb-24 lg:px-7 lg:pb-8">
				<PageHeader eyebrow="Operations at a glance" title="Plant overview"
					:subtitle="`A considered view of every batch, from ingredients to dispatch · ${data.company}`">
					<template #actions>
						<span class="fm-btn-ghost fm-tap flex items-center px-3 text-sm">Last 30 days</span>
						<span class="fm-btn-primary fm-tap flex items-center gap-2 px-4 text-sm">
							<ArrowRight class="h-4 w-4" aria-hidden="true" /> Open production
						</span>
					</template>
				</PageHeader>

				<div class="space-y-4">
					<div class="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
						<KpiCard label="Average actual yield" :value="k.average_yield_percent" unit="%" :decimals="1"
							:icon="TrendingUp" note="2 run(s) outside tolerance" tone="bad" />
						<KpiCard label="Awaiting quality" :value="k.pending_qc" unit="batches" :icon="ShieldCheck"
							note="Ready for a decision" tone="warn" />
						<KpiCard label="Near expiry" :value="k.near_expiry" unit="batches" :icon="Clock"
							note="Within 90 days" tone="warn" />
						<KpiCard label="Open work orders" :value="k.open_runs" unit="runs" :icon="Factory"
							note="Blending &amp; packaging" />
					</div>

					<div class="grid items-start gap-4 lg:grid-cols-[1.6fr_1fr]">
						<div class="rounded-2xl p-5" :style="{ background: 'var(--fm-hero)' }">
							<div class="flex items-start justify-between gap-3">
								<p class="text-[11px] font-bold uppercase tracking-[0.12em]"
									:style="{ color: 'var(--fm-side-ink)' }">Production performance</p>
								<span class="fm-num rounded-full px-2.5 py-1 text-xs font-semibold"
									:style="{ background: 'var(--fm-hero-soft)', color: '#fff' }">
									{{ k.completed_runs }} completed runs
								</span>
							</div>
							<h2 class="mt-2 text-[22px] font-extrabold text-white">Consistency in every run.</h2>
							<p class="mt-1 text-sm" :style="{ color: 'var(--fm-side-ink)' }">
								Actual yield across the most recent completed runs.
							</p>
							<p class="fm-figure mt-4 flex items-baseline gap-1.5">
								<span class="fm-num text-[31px] font-extrabold leading-none text-white">
									{{ k.average_yield_percent.toFixed(1) }}
								</span>
								<span class="text-sm" :style="{ color: 'var(--fm-side-ink)' }">% average yield</span>
							</p>
							<div class="mt-3">
								<LineTrend bare variant="hero" :series="data.yield_trend" title="Actual yield by run" />
							</div>
							<ul class="mt-3 flex flex-wrap gap-4 text-xs" :style="{ color: 'var(--fm-side-ink)' }">
								<li class="flex items-center gap-1.5">
									<span class="h-2 w-2 rounded-full" :style="{ background: 'var(--viz-hero-series)' }" aria-hidden="true" />
									Actual yield by run
								</li>
								<li class="flex items-center gap-1.5">
									<span class="h-2 w-2 rounded-full" :style="{ background: 'var(--viz-hero-flag)' }" aria-hidden="true" />
									Flagged exception
								</li>
							</ul>
						</div>

						<div class="fm-card p-5">
							<div class="flex items-start justify-between gap-2">
								<div>
									<h2 class="text-lg font-bold">Needs your attention</h2>
									<p class="mt-0.5 text-sm fm-muted">A little focus where it matters most.</p>
								</div>
								<span class="fm-chip fm-chip-soft">3 priorities</span>
							</div>
							<ul class="mt-4 space-y-1">
								<li v-for="item in priorities" :key="item.title">
									<span class="fm-tap flex items-center gap-3 rounded-xl px-2">
										<span class="grid h-9 w-9 shrink-0 place-items-center rounded-lg"
											:style="{ background: item.bg, color: item.fg }" aria-hidden="true">
											<component :is="item.icon" class="h-4 w-4" />
										</span>
										<span class="min-w-0 flex-1">
											<span class="block text-sm font-semibold">{{ item.title }}</span>
											<span class="block text-xs fm-muted">{{ item.hint }}</span>
										</span>
										<ChevronRight class="h-4 w-4 shrink-0 fm-muted" aria-hidden="true" />
									</span>
								</li>
							</ul>
							<p class="mt-4 border-t pt-3 text-xs fm-muted" :style="{ borderColor: 'var(--fm-border)' }">
								Company-scoped stock and quality decisions.
							</p>
						</div>
					</div>

					<div class="grid gap-4 lg:grid-cols-2">
						<BarRanking title="Output by item" subtitle="Separate scales for each unit." :rows="outputRows" />
						<div class="space-y-4">
							<StatusStack title="Stock quality" subtitle="63 batches currently holding company stock."
								:rows="data.quality_mix" />
							<BarRanking title="Expiry horizon" subtitle="Most urgent stock first." :rows="expiryRows" :decimals="0" />
						</div>
					</div>

					<ul class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
						<li v-for="action in quickActions" :key="action.label">
							<span class="fm-card fm-tap flex items-center gap-3 p-4">
								<span class="grid h-9 w-9 shrink-0 place-items-center rounded-lg"
									:style="{ background: 'var(--fm-soft)', color: 'var(--fm-primary)' }" aria-hidden="true">
									<component :is="action.icon" class="h-4 w-4" />
								</span>
								<span class="min-w-0 flex-1">
									<span class="block text-sm font-semibold">{{ action.label }}</span>
									<span class="block text-xs fm-muted">{{ action.hint }}</span>
								</span>
								<ArrowRight class="h-4 w-4 shrink-0 fm-muted" aria-hidden="true" />
							</span>
						</li>
					</ul>
				</div>
			</main>
		</div>

		<nav class="fixed inset-x-0 bottom-0 z-30 border-t lg:hidden"
			:style="{ background: 'var(--fm-sidebar)', borderColor: 'rgba(255,255,255,.08)' }">
			<ul class="flex">
				<li v-for="item in phoneNav" :key="item.short" class="flex-1">
					<span class="fm-tap relative flex flex-col items-center justify-center gap-0.5 py-1.5 text-[10px] font-medium"
						:style="{ color: item.active ? '#fff' : 'var(--fm-side-ink)' }">
						<component :is="item.icon" class="h-5 w-5" aria-hidden="true" />
						<span>{{ item.short }}</span>
					</span>
				</li>
			</ul>
		</nav>
	</div>
</template>

<script setup>
import { computed } from 'vue'
import {
	AlertTriangle, ArrowRight, Building2, ChevronRight, ClipboardCheck, Clock, Factory,
	LayoutDashboard, LineChart, PackageCheck, Palette, ShieldCheck, Siren, TrendingUp, Truck,
} from 'lucide-vue-next'

import KpiCard from '@/components/KpiCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import BarRanking from '@/components/viz/BarRanking.vue'
import LineTrend from '@/components/viz/LineTrend.vue'
import StatusStack from '@/components/viz/StatusStack.vue'
import { dashboard as data } from './fixtures.js'

const params = new URLSearchParams(location.search)
const theme = params.get('theme') || 'midnight'
const font = params.get('font') || 'studio'

const k = data.kpis

const nav = [
	{
		label: 'Workspace',
		items: [
			{ label: 'Overview', icon: LayoutDashboard, active: true },
			{ label: 'Production', icon: Factory },
			{ label: 'Quality', icon: ShieldCheck, count: 6 },
			{ label: 'Receiving', icon: PackageCheck },
			{ label: 'Dispatch', icon: Truck },
			{ label: 'Recall', icon: Siren },
		],
	},
	{
		label: 'Insights',
		items: [
			{ label: 'Production insights', icon: LineChart },
			{ label: 'Quality overview', icon: ClipboardCheck },
		],
	},
]

const phoneNav = [
	{ short: 'Overview', icon: LayoutDashboard, active: true },
	{ short: 'Produce', icon: Factory },
	{ short: 'Quality', icon: ShieldCheck },
	{ short: 'Goods in', icon: PackageCheck },
	{ short: 'Dispatch', icon: Truck },
	{ short: 'Recall', icon: Siren },
]

const priorities = [
	{ title: '6 batches need a decision', hint: 'Review quarantined and held batches', icon: ShieldCheck, bg: 'var(--fm-warn-bg)', fg: 'var(--fm-warn)' },
	{ title: '11 batches approaching expiry', hint: 'Stock expiring within the next 90 days', icon: Clock, bg: 'var(--fm-warn-bg)', fg: 'var(--fm-warn)' },
	{ title: '2 runs outside tolerance', hint: 'Check yield exceptions before the next run', icon: AlertTriangle, bg: 'var(--fm-bad-bg)', fg: 'var(--fm-bad)' },
]

const quickActions = [
	{ label: 'Receive ingredients', hint: 'Supplier lots & quantities', icon: PackageCheck },
	{ label: 'Review quality', hint: 'Release, hold or reject', icon: ShieldCheck },
	{ label: 'Complete a run', hint: 'Output & process loss', icon: Factory },
	{ label: 'Prepare a dispatch', hint: 'Eligible batches, FEFO first', icon: Truck },
]

const ORDINAL = ['var(--viz-ordinal-1)', 'var(--viz-ordinal-2)', 'var(--viz-ordinal-3)', 'var(--viz-ordinal-4)']

const outputRows = computed(() =>
	data.production_by_item.map((row) => ({
		key: row.item_code, label: row.label, value: row.value, unit: row.uom,
		note: row.loss ? `${row.runs} run(s) · ${row.loss} ${row.uom} process loss` : `${row.runs} run(s)`,
	}))
)

const expiryRows = computed(() => {
	const ramp = [...ORDINAL].reverse()
	return data.expiry_buckets.map((row, index) => ({
		key: row.label, label: row.label, value: row.value, unit: 'batches',
		color: ramp[Math.min(index, ramp.length - 1)],
	}))
})
</script>

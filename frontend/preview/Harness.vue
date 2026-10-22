<template>
	<div class="fm-app">
		<header class="sticky top-0 z-20 border-b border-gray-200 bg-white/95 backdrop-blur">
			<div class="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3">
				<span
					class="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-white"
					style="background: linear-gradient(135deg, #2a78d6, #1c5cab)"
					aria-hidden="true"
				>
					<Factory class="h-4 w-4" />
				</span>
				<div class="min-w-0">
					<h1 class="truncate text-base font-semibold leading-tight tracking-tight">Food Manufacturing</h1>
					<p class="truncate text-xs text-gray-500">Spice &amp; masala operations</p>
				</div>
				<label class="ml-auto flex items-center gap-2 text-sm">
					<span class="fm-label hidden sm:inline">Company</span>
					<select class="fm-tap rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-sm font-medium">
						<option>{{ data.company }}</option>
					</select>
				</label>
			</div>
			<nav aria-label="Sections" class="mx-auto max-w-7xl overflow-x-auto px-2">
				<ul class="flex min-w-max gap-1 pb-2">
					<li v-for="(item, index) in nav" :key="item.label">
						<span
							class="fm-tap flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium"
							:class="index === 0 ? 'bg-gray-900 text-white' : 'text-gray-700'"
						>
							<component :is="item.icon" class="h-4 w-4" aria-hidden="true" />
							{{ item.label }}
							<span
								v-if="item.count"
								class="rounded-full px-1.5 text-xs font-semibold"
								:class="index === 0 ? 'bg-white/20 text-white' : 'bg-gray-200 text-gray-800'"
							>{{ item.count }}</span>
						</span>
					</li>
				</ul>
			</nav>
		</header>

		<main class="mx-auto max-w-7xl px-4 py-5">
			<div class="mb-5 flex flex-wrap items-end justify-between gap-3">
				<div>
					<h2 class="text-xl font-semibold tracking-tight">Plant overview</h2>
					<p class="text-sm text-gray-600">{{ data.company }} · last {{ data.period_days }} days</p>
				</div>
				<div class="flex items-center gap-2">
					<select class="fm-tap rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm">
						<option>Last 30 days</option>
					</select>
					<button class="fm-tap rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium">
						Refresh
					</button>
				</div>
			</div>

			<div class="space-y-5">
				<div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
					<StatTile hero class="col-span-2 lg:col-span-1" label="Average actual yield" :value="k.average_yield_percent" unit="%" :decimals="1"
						:icon="TrendingUp" note="2 run(s) outside tolerance" note-role="critical" :note-icon="TrendingDown"
						hint="Output over input across completed runs" />
					<StatTile label="Pending quality" :value="k.pending_qc" :icon="ClipboardCheck"
						note="Awaiting a decision" note-role="warning" :note-icon="AlertTriangle" />
					<StatTile label="Near expiry" :value="k.near_expiry" :icon="CalendarClock"
						note="Within 90 days" note-role="serious" :note-icon="AlertTriangle" />
					<StatTile label="Yield variance flagged" :value="k.yield_flagged" :icon="Activity"
						note="Outside tolerance" note-role="critical" :note-icon="AlertTriangle" />
				</div>

				<div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
					<StatTile label="Runs completed" :value="k.completed_runs" :icon="Factory" />
					<StatTile label="Runs open now" :value="k.open_runs" :icon="Timer" />
					<StatTile label="Batches released" :value="k.batches_released" :icon="BadgeCheck" />
				</div>

				<LineTrend title="Actual yield by run"
					subtitle="Most recent runs, oldest first. Flagged runs are marked and labelled."
					:series="data.yield_trend" />

				<div class="grid items-start gap-3 lg:grid-cols-2">
					<BarRanking title="Output by item" subtitle="Highest first. Each row is in its own unit."
						:rows="productionRows" />
					<div class="space-y-3">
						<StatusStack title="Stock by quality status" subtitle="Batches holding stock in this company."
							:rows="data.quality_mix" />
						<BarRanking title="Expiry horizon"
							subtitle="Batch counts by how close they are to expiry, most urgent first."
							:rows="expiryRows" :decimals="0" />
					</div>
				</div>
			</div>
		</main>
	</div>
</template>

<script setup>
import { computed } from 'vue'
import {
	Activity, AlertTriangle, BadgeCheck, CalendarClock, ClipboardCheck,
	Factory, LayoutDashboard, PackageCheck, Timer, TrendingDown, TrendingUp, Truck,
} from 'lucide-vue-next'

import BarRanking from '@/components/viz/BarRanking.vue'
import LineTrend from '@/components/viz/LineTrend.vue'
import StatTile from '@/components/viz/StatTile.vue'
import StatusStack from '@/components/viz/StatusStack.vue'
import { dashboard as data } from './fixtures.js'

const k = data.kpis

const nav = [
	{ label: 'Overview', icon: LayoutDashboard },
	{ label: 'Production', icon: Factory },
	{ label: 'Quality', icon: ClipboardCheck, count: 6 },
	{ label: 'Receiving', icon: PackageCheck },
	{ label: 'Dispatch', icon: Truck },
]

const productionRows = computed(() =>
	data.production_by_item.map((row) => ({
		key: row.item_code,
		label: row.label,
		value: row.value,
		unit: row.uom,
		note: row.loss ? `${row.runs} run(s) · ${row.loss} ${row.uom} process loss` : `${row.runs} run(s)`,
	}))
)

const ORDINAL = [
	'var(--viz-ordinal-1)', 'var(--viz-ordinal-2)',
	'var(--viz-ordinal-3)', 'var(--viz-ordinal-4)',
]

const expiryRows = computed(() => {
	const ramp = [...ORDINAL].reverse()
	return data.expiry_buckets.map((row, index) => ({
		key: row.label,
		label: row.label,
		value: row.value,
		unit: 'batches',
		color: ramp[Math.min(index, ramp.length - 1)],
	}))
})
</script>

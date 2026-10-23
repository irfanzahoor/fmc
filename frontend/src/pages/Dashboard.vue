<template>
	<section>
		<PageHeader
			eyebrow="Operations at a glance"
			title="Plant overview"
			:subtitle="`A considered view of every batch, from ingredients to dispatch · ${company}`"
		>
			<template #actions>
				<label class="flex items-center">
					<span class="sr-only">Period</span>
					<select v-model.number="days" class="fm-btn-ghost fm-tap px-3 text-sm" @change="load">
						<option :value="7">Last 7 days</option>
						<option :value="30">Last 30 days</option>
						<option :value="90">Last 90 days</option>
					</select>
				</label>
				<RouterLink :to="{ name: 'Production' }" class="fm-btn-primary fm-tap flex items-center gap-2 px-4 text-sm">
					<ArrowRight class="h-4 w-4" aria-hidden="true" />
					Open production
				</RouterLink>
			</template>
		</PageHeader>

		<StateBlock :loading="loading && !data" :error="error" loading-text="Building the overview…" :on-retry="load" :required-roles="SCREEN_ROLES.overview">
			<div v-if="data" class="space-y-4">
				<div class="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
					<KpiCard
						label="Average actual yield" :value="k.average_yield_percent" unit="%" :decimals="1"
						:icon="TrendingUp" :note="yieldNote" :tone="yieldTone" :trend="yieldSpark"
					/>
					<KpiCard
						label="Awaiting quality" :value="k.pending_qc" unit="batches" :icon="ShieldCheck"
						:note="k.pending_qc ? 'Ready for a decision' : 'Queue is clear'"
						:tone="k.pending_qc ? 'warn' : 'good'"
					/>
					<KpiCard
						label="Near expiry" :value="k.near_expiry" unit="batches" :icon="Clock"
						:note="k.near_expiry ? 'Within 90 days' : 'Nothing expiring soon'"
						:tone="k.near_expiry ? 'warn' : 'good'"
					/>
					<KpiCard
						label="Open work orders" :value="k.open_runs" unit="runs" :icon="Factory"
						note="Blending &amp; packaging" tone="neutral"
					/>
				</div>

				<div class="grid items-start gap-4 lg:grid-cols-[1.6fr_1fr]">
					<!-- One focal point: the dark panel, not every card equally weighted. -->
					<div class="rounded-2xl p-5" :style="{ background: 'var(--fm-hero)' }">
						<div class="flex items-start justify-between gap-3">
							<p class="text-[11px] font-bold uppercase tracking-[0.12em]" :style="{ color: 'var(--fm-side-ink)' }">
								Production performance
							</p>
							<span
								class="fm-num rounded-full px-2.5 py-1 text-xs font-semibold"
								:style="{ background: 'var(--fm-hero-soft)', color: '#fff' }"
							>
								{{ k.completed_runs }} completed runs
							</span>
						</div>

						<h2 class="mt-2 text-[22px] font-extrabold text-white">Consistency in every run.</h2>
						<p class="mt-1 text-sm" :style="{ color: 'var(--fm-side-ink)' }">
							Actual yield across the most recent completed runs.
						</p>

						<!-- The one hero figure on this view, set above the stat
						     row's 31px so the panel reads as the focal point.
						     Proportional figures: it stands alone. -->
						<p class="fm-figure mt-4 flex items-baseline gap-1.5">
							<span class="text-[44px] font-extrabold leading-none text-white">
								{{ heroYield }}
							</span>
							<span class="text-sm" :style="{ color: 'var(--fm-side-ink)' }">
								{{ k.average_yield_percent === null ? 'no completed runs' : '% average yield' }}
							</span>
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

					<!-- The rail carries two cards so it stands as tall as the
					     hero beside it; one short card left the column half empty. -->
					<div class="space-y-4">
						<div class="fm-card p-5">
						<div class="flex items-start justify-between gap-2">
							<div>
								<h2 class="text-lg font-bold">Needs your attention</h2>
								<p class="mt-0.5 text-sm fm-muted">A little focus where it matters most.</p>
							</div>
							<span v-if="priorities.length" class="fm-chip fm-chip-soft">
								{{ priorities.length }} {{ priorities.length === 1 ? 'priority' : 'priorities' }}
							</span>
						</div>

						<ul v-if="priorities.length" class="mt-4 space-y-1">
							<li v-for="item in priorities" :key="item.title">
								<RouterLink
									:to="item.to"
									class="fm-tap flex items-center gap-3 rounded-xl px-2 text-left transition-colors hover:bg-[var(--fm-canvas)] motion-reduce:transition-none"
								>
									<span
										class="grid h-9 w-9 shrink-0 place-items-center rounded-lg"
										:style="{ background: item.bg, color: item.fg }"
										aria-hidden="true"
									>
										<component :is="item.icon" class="h-4 w-4" />
									</span>
									<span class="min-w-0 flex-1">
										<span class="block text-sm font-semibold">{{ item.title }}</span>
										<span class="block text-xs fm-muted">{{ item.hint }}</span>
									</span>
									<ChevronRight class="h-4 w-4 shrink-0 fm-muted" aria-hidden="true" />
								</RouterLink>
							</li>
						</ul>

						<p v-else class="mt-6 flex items-center gap-2 text-sm" :style="{ color: 'var(--fm-good)' }">
							<CheckCircle class="h-4 w-4" aria-hidden="true" />
							Nothing needs attention right now.
						</p>

						<p class="mt-4 border-t pt-3 text-xs fm-muted" :style="{ borderColor: 'var(--fm-border)' }">
							Company-scoped stock and quality decisions.
						</p>
						</div>

						<StatusStack
							title="Stock quality"
							:subtitle="`${qualityTotal} batches currently holding company stock.`"
							:rows="data.quality_mix"
						/>
					</div>
				</div>

				<div class="grid items-start gap-4 lg:grid-cols-2">
					<BarRanking
						title="Output by item"
						subtitle="Separate scales for each unit."
						:rows="productionRows"
						empty-text="No output recorded in this period."
					/>

					<ColumnBuckets
						title="Expiry horizon"
						subtitle="Batches by how close they are to expiry. Most urgent on the left."
						:rows="expiryRows"
						unit-label="batches"
						footnote="Rejected batches are left out: they are already out of use."
						empty-text="No batch expires within 90 days."
					/>
				</div>

				<ul class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
					<li v-for="action in quickActions" :key="action.label">
						<RouterLink :to="action.to" class="fm-card fm-tap flex items-center gap-3 p-4 transition-colors hover:border-[var(--fm-primary)] motion-reduce:transition-none">
							<span
								class="grid h-9 w-9 shrink-0 place-items-center rounded-lg"
								:style="{ background: 'var(--fm-soft)', color: 'var(--fm-primary)' }"
								aria-hidden="true"
							>
								<component :is="action.icon" class="h-4 w-4" />
							</span>
							<span class="min-w-0 flex-1">
								<span class="block text-sm font-semibold">{{ action.label }}</span>
								<span class="block text-xs fm-muted">{{ action.hint }}</span>
							</span>
							<ArrowRight class="h-4 w-4 shrink-0 fm-muted" aria-hidden="true" />
						</RouterLink>
					</li>
				</ul>
			</div>
		</StateBlock>
	</section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
	AlertTriangle,
	ArrowRight,
	CheckCircle,
	ChevronRight,
	Clock,
	Factory,
	PackageCheck,
	ShieldCheck,
	TrendingUp,
	Truck,
} from 'lucide-vue-next'

import KpiCard from '@/components/KpiCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import { SCREEN_ROLES } from '@/data/access'
import { dashboard } from '@/data/api'
import BarRanking from '@/components/viz/BarRanking.vue'
import ColumnBuckets from '@/components/viz/ColumnBuckets.vue'
import LineTrend from '@/components/viz/LineTrend.vue'
import StatusStack from '@/components/viz/StatusStack.vue'

const props = defineProps({ company: { type: String, required: true } })

const data = ref(null)
const loading = ref(false)
const error = ref(null)
const days = ref(30)

const k = computed(() => data.value?.kpis || {})

const heroYield = computed(() =>
	k.value.average_yield_percent === null || k.value.average_yield_percent === undefined
		? '—'
		: Number(k.value.average_yield_percent).toFixed(1)
)

const qualityTotal = computed(() =>
	(data.value?.quality_mix || []).reduce((sum, row) => sum + Number(row.value || 0), 0)
)

/* Ordinal ramp, darkest = most urgent. The API returns most urgent first. */

const productionRows = computed(() =>
	(data.value?.production_by_item || []).map((row) => ({
		key: row.item_code,
		label: row.label,
		value: row.value,
		unit: row.uom,
		note: row.loss ? `${row.runs} run(s) · ${row.loss} ${row.uom} process loss` : `${row.runs} run(s)`,
	}))
)

/*
 * The expiry scale, and the ramp step each bucket owns.
 *
 * `expiry_buckets` leaves out a bucket with no batches in it, so stepping the
 * ramp by row position would repaint the rest on a day when "Expired" is empty:
 * "Within 7 days" would wear the darkest step one day and the second the next.
 * The step follows the bucket. Kept in step with EXPIRY_BUCKETS in
 * `food_manufacturing/api/dashboard.py`.
 */
const EXPIRY_STEP = {
	Expired: 'var(--viz-ordinal-4)',
	'Within 7 days': 'var(--viz-ordinal-3)',
	'8-30 days': 'var(--viz-ordinal-2)',
	'31-90 days': 'var(--viz-ordinal-1)',
}

const expiryRows = computed(() =>
	(data.value?.expiry_buckets || []).map((row) => ({
		label: row.label,
		value: row.value,
		color: EXPIRY_STEP[row.label],
	}))
)

/* The stat tile's trend: the same completed runs the panel plots, as a mark
   rather than a second chart. */
const yieldSpark = computed(() =>
	(data.value?.yield_trend || []).map((row) => Number(row.actual)).filter(Number.isFinite)
)

const yieldNote = computed(() => {
	if (k.value.average_yield_percent === null || k.value.average_yield_percent === undefined) {
		return 'No completed runs in this period'
	}
	return k.value.yield_flagged ? `${k.value.yield_flagged} run(s) outside tolerance` : 'Across completed runs'
})

const yieldTone = computed(() => {
	if (k.value.average_yield_percent === null || k.value.average_yield_percent === undefined) return 'neutral'
	return k.value.yield_flagged ? 'bad' : 'good'
})

/* Only real counts become priorities; nothing is invented to fill the card. */
const priorities = computed(() => {
	const items = []
	if (k.value.pending_qc) {
		items.push({
			title: `${k.value.pending_qc} batch(es) need a decision`,
			hint: 'Review quarantined and held batches',
			icon: ShieldCheck,
			bg: 'var(--fm-warn-bg)',
			fg: 'var(--fm-warn)',
			to: { name: 'Quality' },
		})
	}
	if (k.value.near_expiry) {
		items.push({
			title: `${k.value.near_expiry} batch(es) approaching expiry`,
			hint: 'Stock expiring within the next 90 days',
			icon: Clock,
			bg: 'var(--fm-warn-bg)',
			fg: 'var(--fm-warn)',
			to: { name: 'Dispatch' },
		})
	}
	if (k.value.yield_flagged) {
		items.push({
			title: `${k.value.yield_flagged} run(s) outside tolerance`,
			hint: 'Check yield exceptions before the next run',
			icon: AlertTriangle,
			bg: 'var(--fm-bad-bg)',
			fg: 'var(--fm-bad)',
			to: { name: 'ProductionInsights' },
		})
	}
	return items
})

const quickActions = [
	{ label: 'Receive ingredients', hint: 'Supplier lots & quantities', icon: PackageCheck, to: { name: 'Receiving' } },
	{ label: 'Review quality', hint: 'Release, hold or reject', icon: ShieldCheck, to: { name: 'Quality' } },
	{ label: 'Complete a run', hint: 'Output & process loss', icon: Factory, to: { name: 'Production' } },
	{ label: 'Prepare a dispatch', hint: 'Eligible batches, FEFO first', icon: Truck, to: { name: 'Dispatch' } },
]

async function load() {
	loading.value = true
	error.value = null
	try {
		data.value = await dashboard.get({ company: props.company, days: days.value })
	} catch (err) {
		error.value = err
	} finally {
		loading.value = false
	}
}

onMounted(load)
</script>

<template>
	<section aria-labelledby="fm-dash-heading">
		<div class="mb-5 flex flex-wrap items-end justify-between gap-3">
			<div>
				<h2 id="fm-dash-heading" class="text-xl font-semibold tracking-tight">Plant overview</h2>
				<p class="text-sm text-gray-600">
					{{ company }} · last {{ data?.period_days || days }} days
				</p>
			</div>

			<div class="flex items-center gap-2">
				<!-- Filters sit in one row above the charts. -->
				<label class="flex items-center gap-2 text-sm">
					<span class="sr-only">Period</span>
					<select
						v-model.number="days"
						class="fm-tap rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm"
						@change="load"
					>
						<option :value="7">Last 7 days</option>
						<option :value="30">Last 30 days</option>
						<option :value="90">Last 90 days</option>
					</select>
				</label>
				<Button class="fm-tap" :loading="loading" @click="load">Refresh</Button>
			</div>
		</div>

		<StateBlock
			:loading="loading && !data"
			:error="error"
			loading-text="Building the overview…"
			:on-retry="load"
		>
			<div v-if="data" class="space-y-5">
				<!-- Hero figure plus the KPI row. A single current value is a stat
				     tile, never a one-bar chart. -->
				<div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
					<StatTile
						hero
						class="col-span-2 lg:col-span-1"
						label="Average actual yield"
						:value="k.average_yield_percent"
						unit="%"
						:decimals="1"
						:icon="TrendingUp"
						:note="yieldNote"
						:note-role="yieldRole"
						:note-icon="yieldIcon"
						hint="Output over input across completed runs"
					/>
					<StatTile
						label="Pending quality"
						:value="k.pending_qc"
						:icon="ClipboardCheck"
						:note="k.pending_qc ? 'Awaiting a decision' : 'Queue is clear'"
						:note-role="k.pending_qc ? 'warning' : 'good'"
						:note-icon="k.pending_qc ? AlertTriangle : CheckCircle"
					/>
					<StatTile
						label="Near expiry"
						:value="k.near_expiry"
						:icon="CalendarClock"
						:note="k.near_expiry ? 'Within 90 days' : 'Nothing expiring soon'"
						:note-role="k.near_expiry ? 'serious' : 'good'"
						:note-icon="k.near_expiry ? AlertTriangle : CheckCircle"
					/>
					<StatTile
						label="Yield variance flagged"
						:value="k.yield_flagged"
						:icon="Activity"
						:note="k.yield_flagged ? 'Outside tolerance' : 'All runs within tolerance'"
						:note-role="k.yield_flagged ? 'critical' : 'good'"
						:note-icon="k.yield_flagged ? AlertTriangle : CheckCircle"
					/>
				</div>

				<div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
					<StatTile label="Runs completed" :value="k.completed_runs" :icon="Factory" />
					<StatTile label="Runs open now" :value="k.open_runs" :icon="Timer" />
					<StatTile label="Batches released" :value="k.batches_released" :icon="BadgeCheck" />
				</div>

				<LineTrend
					title="Actual yield by run"
					subtitle="Most recent runs, oldest first. Flagged runs are marked and labelled."
					:series="data.yield_trend"
				/>

				<!-- items-start so a short card sizes to its content instead of
				     stretching into a tall empty box beside a long one. -->
				<div class="grid items-start gap-3 lg:grid-cols-2">
					<BarRanking
						title="Output by item"
						subtitle="Highest first. Each row is in its own unit."
						:rows="productionRows"
						empty-text="No output recorded in this period."
					/>

					<div class="space-y-3">
						<StatusStack
							title="Stock by quality status"
							subtitle="Batches holding stock in this company."
							:rows="data.quality_mix"
						/>
						<BarRanking
							title="Expiry horizon"
							subtitle="Batch counts by how close they are to expiry, most urgent first."
							:rows="expiryRows"
							:decimals="0"
							empty-text="No batch expires within 90 days."
						/>
					</div>
				</div>
			</div>
		</StateBlock>
	</section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
	Activity,
	AlertTriangle,
	BadgeCheck,
	CalendarClock,
	CheckCircle,
	ClipboardCheck,
	Factory,
	Timer,
	TrendingDown,
	TrendingUp,
} from 'lucide-vue-next'

import StateBlock from '@/components/StateBlock.vue'
import BarRanking from '@/components/viz/BarRanking.vue'
import LineTrend from '@/components/viz/LineTrend.vue'
import StatTile from '@/components/viz/StatTile.vue'
import StatusStack from '@/components/viz/StatusStack.vue'
import { call } from 'frappe-ui'

const props = defineProps({ company: { type: String, required: true } })

const data = ref(null)
const loading = ref(false)
const error = ref(null)
const days = ref(30)

const k = computed(() => data.value?.kpis || {})

/* The ordinal ramp runs light -> dark with urgency, so the most urgent bucket
   is the darkest. The bucket label carries the meaning; colour reinforces. */
const ORDINAL = [
	'var(--viz-ordinal-1)',
	'var(--viz-ordinal-2)',
	'var(--viz-ordinal-3)',
	'var(--viz-ordinal-4)',
]

const productionRows = computed(() =>
	(data.value?.production_by_item || []).map((row) => ({
		key: row.item_code,
		label: row.label,
		value: row.value,
		unit: row.uom,
		note: row.loss ? `${row.runs} run(s) · ${row.loss} ${row.uom} process loss` : `${row.runs} run(s)`,
	}))
)

const expiryRows = computed(() => {
	const buckets = data.value?.expiry_buckets || []
	// The API returns most urgent first, so walk the ramp from its darkest
	// step down: urgency is carried by position, colour and the label itself.
	const ramp = [...ORDINAL].reverse()
	return buckets.map((row, index) => ({
		key: row.label,
		label: row.label,
		value: row.value,
		unit: 'batches',
		color: ramp[Math.min(index, ramp.length - 1)],
	}))
})

const yieldNote = computed(() => {
	if (k.value.average_yield_percent === null || k.value.average_yield_percent === undefined) {
		return 'No completed runs in this period'
	}
	return k.value.yield_flagged
		? `${k.value.yield_flagged} run(s) outside tolerance`
		: 'Within tolerance'
})

const yieldRole = computed(() => {
	if (k.value.average_yield_percent === null || k.value.average_yield_percent === undefined) return ''
	return k.value.yield_flagged ? 'critical' : 'good'
})

const yieldIcon = computed(() => (k.value.yield_flagged ? TrendingDown : CheckCircle))

async function load() {
	loading.value = true
	error.value = null
	try {
		data.value = await call('food_manufacturing.api.dashboard.get_dashboard', {
			company: props.company,
			days: days.value,
		})
	} catch (err) {
		error.value = err
	} finally {
		loading.value = false
	}
}

onMounted(load)
</script>

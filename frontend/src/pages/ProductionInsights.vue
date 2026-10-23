<template>
	<section>
		<PageHeader
			eyebrow="Production workspace"
			title="Production insights"
			subtitle="Yield, loss and output across completed runs."
			:tabs="tabs"
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
				<button type="button" class="fm-btn-ghost fm-tap flex items-center gap-2 px-3 text-sm" @click="load">
					<RefreshCw class="h-4 w-4" aria-hidden="true" />
					Refresh
				</button>
			</template>
		</PageHeader>

		<StateBlock :loading="loading && !data" :error="error" loading-text="Loading insights…" :on-retry="load">
			<div v-if="data" class="space-y-4">
				<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
					<KpiCard label="Average actual yield" :value="k.average_yield_percent" unit="%" :decimals="1"
						:icon="TrendingUp" :note="k.average_yield_percent === null ? 'No completed runs' : 'Across completed runs'"
						:tone="k.average_yield_percent === null ? 'neutral' : 'good'" />
					<KpiCard label="Runs completed" :value="k.completed_runs" :icon="CheckCircle" />
					<KpiCard label="Runs open now" :value="k.open_runs" :icon="Factory" />
					<KpiCard label="Outside tolerance" :value="k.yield_flagged" unit="runs" :icon="AlertTriangle"
						:note="k.yield_flagged ? 'Review before the next run' : 'All runs within tolerance'"
						:tone="k.yield_flagged ? 'bad' : 'good'" />
				</div>

				<LineTrend
					title="Actual yield by run"
					subtitle="Oldest first. Flagged runs are marked and labelled; the dashed line is the planned yield."
					:series="data.yield_trend"
				/>

				<div class="grid gap-4 lg:grid-cols-2">
					<BarRanking title="Output by item" subtitle="Separate scales for each unit."
						:rows="outputRows" empty-text="No output recorded in this period." />
					<BarRanking title="Process loss by item" subtitle="Non-recoverable loss, in each item's own unit."
						:rows="lossRows" empty-text="No process loss recorded in this period." />
				</div>

				<p class="text-xs fm-muted">
					Figures come from completed Work Orders in this company. A run whose ingredients use mixed
					units has no computable yield and is left out of the trend rather than plotted as zero.
				</p>
			</div>
		</StateBlock>
	</section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { AlertTriangle, CheckCircle, Factory, LineChart, RefreshCw, TrendingUp } from 'lucide-vue-next'
import { call } from 'frappe-ui'

import KpiCard from '@/components/KpiCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import BarRanking from '@/components/viz/BarRanking.vue'
import LineTrend from '@/components/viz/LineTrend.vue'

const props = defineProps({ company: { type: String, required: true } })

const data = ref(null)
const loading = ref(false)
const error = ref(null)
const days = ref(30)

const k = computed(() => data.value?.kpis || {})

const tabs = [
	{ name: 'Production', label: 'Workspace', icon: Factory },
	{ name: 'ProductionInsights', label: 'Insights', icon: LineChart },
]

const outputRows = computed(() =>
	(data.value?.production_by_item || []).map((row) => ({
		key: row.item_code,
		label: row.label,
		value: row.value,
		unit: row.uom,
		note: `${row.runs} run(s)`,
	}))
)

/* Only items that actually recorded loss; a zero row would imply a measurement
   that was never taken. */
const lossRows = computed(() =>
	(data.value?.production_by_item || [])
		.filter((row) => Number(row.loss) > 0)
		.map((row) => ({
			key: `${row.item_code}-loss`,
			label: row.label,
			value: row.loss,
			unit: row.uom,
			color: 'var(--viz-ordinal-3)',
		}))
)

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

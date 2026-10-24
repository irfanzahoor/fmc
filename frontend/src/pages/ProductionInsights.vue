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

		<StateBlock :loading="loading && !data" :error="error" loading-text="Loading insights…" :on-retry="load" :required-roles="SCREEN_ROLES.overview">
			<div v-if="data" class="space-y-4">
				<div class="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
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
					<BarRanking
						title="Process loss rate"
						subtitle="Non-recoverable loss as a share of what went in. One scale, so items compare."
						:rows="lossRows"
						:show-share="false"
						empty-text="No process loss recorded in this period."
					/>
				</div>

				<!-- The rows behind the flag. A chart can say a run was outside
				     tolerance; only this says by how much, and on what quantity. -->
				<RunReview :rows="data.yield_exceptions || []" />

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

import KpiCard from '@/components/KpiCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import { SCREEN_ROLES } from '@/data/access'
import { dashboard } from '@/data/api'
import BarRanking from '@/components/viz/BarRanking.vue'
import LineTrend from '@/components/viz/LineTrend.vue'
import RunReview from '@/components/viz/RunReview.vue'

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
		nature: row.nature,
		note: `${row.runs} run(s)`,
	}))
)

/*
 * Loss as a share of what went in, not as a raw quantity.
 *
 * Ranked by kilograms, the biggest product always looks like the worst
 * offender: 56 kg lost on 1,842 kg is 3%, while 34 kg lost on 420 kg is 8% -
 * the chart named the wrong item. A rate also puts every item on one scale, so
 * these bars are comparable where the output bars are not.
 *
 * Only items that actually recorded loss; a zero row would imply a measurement
 * that was never taken.
 */
const lossRows = computed(() =>
	(data.value?.production_by_item || [])
		.filter((row) => Number(row.loss) > 0)
		.map((row) => {
			const loss = Number(row.loss)
			const input = Number(row.value) + loss
			return {
				key: `${row.item_code}-loss`,
				label: row.label,
				value: input > 0 ? Math.round((loss / input) * 1000) / 10 : 0,
				unit: '%',
				note: `${formatQty(loss)} of ${formatQty(input)} ${row.uom}`,
				color: 'var(--viz-series-2)',
			}
		})
)

const formatQty = (value) =>
	Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })

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

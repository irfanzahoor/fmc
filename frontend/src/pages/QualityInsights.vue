<template>
	<section>
		<PageHeader
			eyebrow="Quality workspace"
			title="Quality overview"
			subtitle="Where stock sits, and what is running out of time."
			:tabs="tabs"
		>
			<template #actions>
				<button type="button" class="fm-btn-ghost fm-tap flex items-center gap-2 px-3 text-sm" @click="load">
					<RefreshCw class="h-4 w-4" aria-hidden="true" />
					Refresh
				</button>
			</template>
		</PageHeader>

		<StateBlock :loading="loading && !data" :error="error" loading-text="Loading quality overview…" :on-retry="load">
			<div v-if="data" class="space-y-4">
				<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
					<KpiCard label="Awaiting a decision" :value="k.pending_qc" unit="batches" :icon="ShieldCheck"
						:note="k.pending_qc ? 'Quarantined or held' : 'Queue is clear'"
						:tone="k.pending_qc ? 'warn' : 'good'" />
					<KpiCard label="Released in period" :value="k.batches_released" unit="batches" :icon="CheckCircle" tone="good" />
					<KpiCard label="Near expiry" :value="k.near_expiry" unit="batches" :icon="Clock"
						:note="k.near_expiry ? 'Within 90 days' : 'Nothing expiring soon'"
						:tone="k.near_expiry ? 'warn' : 'good'" />
					<KpiCard label="Holding stock" :value="qualityTotal" unit="batches" :icon="Boxes" />
				</div>

				<div class="grid gap-4 lg:grid-cols-2">
					<StatusStack
						title="Stock by quality status"
						:subtitle="`${qualityTotal} batches currently holding company stock.`"
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

				<div class="fm-card p-5">
					<h2 class="text-base font-bold">Act on the queue</h2>
					<p class="mt-0.5 text-sm fm-muted">
						Decisions are audited. Release, hold and reject each record who decided and why.
					</p>
					<RouterLink :to="{ name: 'Quality' }" class="fm-btn-primary fm-tap mt-3 inline-flex items-center gap-2 px-4 text-sm">
						<ArrowRight class="h-4 w-4" aria-hidden="true" />
						Open the quality queue
					</RouterLink>
				</div>

				<p class="text-xs fm-muted">
					Counts cover batches holding stock in this company only. Rejected batches are excluded from the
					expiry horizon because they are already out of use.
				</p>
			</div>
		</StateBlock>
	</section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ArrowRight, Boxes, CheckCircle, ClipboardCheck, Clock, RefreshCw, ShieldCheck } from 'lucide-vue-next'

import KpiCard from '@/components/KpiCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import { dashboard } from '@/data/api'
import BarRanking from '@/components/viz/BarRanking.vue'
import StatusStack from '@/components/viz/StatusStack.vue'

const props = defineProps({ company: { type: String, required: true } })

const data = ref(null)
const loading = ref(false)
const error = ref(null)

const k = computed(() => data.value?.kpis || {})

const tabs = [
	{ name: 'Quality', label: 'Workspace', icon: ShieldCheck },
	{ name: 'QualityInsights', label: 'Insights', icon: ClipboardCheck },
]

const qualityTotal = computed(() =>
	(data.value?.quality_mix || []).reduce((sum, row) => sum + Number(row.value || 0), 0)
)

const ORDINAL = ['var(--viz-ordinal-1)', 'var(--viz-ordinal-2)', 'var(--viz-ordinal-3)', 'var(--viz-ordinal-4)']

const expiryRows = computed(() => {
	const ramp = [...ORDINAL].reverse()
	return (data.value?.expiry_buckets || []).map((row, index) => ({
		key: row.label,
		label: row.label,
		value: row.value,
		unit: 'batches',
		color: ramp[Math.min(index, ramp.length - 1)],
	}))
})

async function load() {
	loading.value = true
	error.value = null
	try {
		data.value = await dashboard.get({ company: props.company, days: 90 })
	} catch (err) {
		error.value = err
	} finally {
		loading.value = false
	}
}

onMounted(load)
</script>

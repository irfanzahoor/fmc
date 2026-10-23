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
				<RouterLink :to="{ name: 'Quality' }" class="fm-btn-primary fm-tap flex items-center gap-2 px-4 text-sm">
					Open the queue
					<ArrowRight class="h-4 w-4" aria-hidden="true" />
				</RouterLink>
			</template>
		</PageHeader>

		<StateBlock :loading="loading && !data" :error="error" loading-text="Loading quality overview…" :on-retry="load" :required-roles="SCREEN_ROLES.overview">
			<div v-if="data" class="space-y-4">
				<div class="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
					<KpiCard label="Awaiting a decision" :value="k.pending_qc" unit="batches" :icon="ShieldCheck"
						:note="k.pending_qc ? 'Quarantined or held' : 'Queue is clear'"
						:tone="k.pending_qc ? 'warn' : 'good'" />
					<KpiCard label="Released in period" :value="k.batches_released" unit="batches" :icon="CheckCircle" tone="good" />
					<KpiCard label="Near expiry" :value="k.near_expiry" unit="batches" :icon="Clock"
						:note="k.near_expiry ? 'Within 90 days' : 'Nothing expiring soon'"
						:tone="k.near_expiry ? 'warn' : 'good'" />
					<KpiCard label="Holding stock" :value="qualityTotal" unit="batches" :icon="Boxes" />
				</div>

				<!-- The expiry ranking carries four labelled rows to the stack's
				     one bar, so it gets the wider column rather than an equal half. -->
				<div class="grid items-start gap-4 lg:grid-cols-5">
					<StatusStack
						class="lg:col-span-2"
						title="Stock by quality status"
						:subtitle="`${qualityTotal} batches currently holding company stock.`"
						:rows="data.quality_mix"
					/>
					<ColumnBuckets
						class="lg:col-span-3"
						title="Expiry horizon"
						subtitle="Batches by how close they are to expiry. Most urgent on the left."
						:rows="expiryRows"
						unit-label="batches"
						empty-text="No batch expires within 90 days."
					/>
				</div>

				<p class="text-xs fm-muted">
					Counts cover batches holding stock in this company only. Rejected batches are excluded from the
					expiry horizon because they are already out of use. Every release, hold and reject is audited
					with who decided and why.
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
import { SCREEN_ROLES } from '@/data/access'
import { dashboard } from '@/data/api'
import ColumnBuckets from '@/components/viz/ColumnBuckets.vue'
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

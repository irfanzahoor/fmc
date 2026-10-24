<template>
	<section>
		<PageHeader
			eyebrow="Quality workspace"
			title="Quality"
			subtitle="Every batch deserves a clear, considered decision."
			:tabs="tabs"
		>
			<template #actions>
				<button type="button" class="fm-btn-ghost fm-tap flex items-center gap-2 px-3 text-sm" @click="reload">
					<RefreshCw class="h-4 w-4" :class="loading ? 'animate-spin motion-reduce:animate-none' : ''" aria-hidden="true" />
					Refresh
				</button>
			</template>
		</PageHeader>

		<!-- Counts come from the queue endpoint; "released" from the dashboard.
		     Nothing here is derived from the page currently on screen. -->
		<div class="mb-4 grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
			<KpiCard label="Awaiting a decision" :value="counts.total" unit="batches" :icon="ShieldCheck"
				note="Company-stock queue" :tone="counts.total ? 'warn' : 'good'" />
			<KpiCard label="In quarantine" :value="counts.quarantine" unit="batches" :icon="Boxes"
				note="Inspection & review pending" />
			<KpiCard label="Currently on hold" :value="counts.hold" unit="batches" :icon="PauseCircle"
				note="Follow-up required" />
			<KpiCard label="Released in period" :value="releasedInPeriod" unit="batches" :icon="CheckCircle"
				note="Audited decisions" tone="good" />
		</div>

		<!-- Filters in one row above the queue. -->
		<div class="mb-3 flex flex-wrap items-center gap-2">
			<div class="flex gap-1" role="group" aria-label="Status filter">
				<button
					v-for="option in statusFilters"
					:key="option.value"
					type="button"
					class="fm-tap rounded-lg px-3 text-sm font-medium"
					:style="status === option.value
						? { background: 'var(--fm-soft)', color: 'var(--fm-primary)', border: '1px solid var(--fm-primary)' }
						: { border: '1px solid var(--fm-border)', background: 'var(--fm-surface)' }"
					:aria-pressed="status === option.value"
					@click="setStatus(option.value)"
				>
					{{ option.label }}
				</button>
			</div>

			<label class="ml-auto flex min-w-[14rem] flex-1 items-center gap-2 sm:max-w-xs">
				<span class="sr-only">Filter the loaded batches</span>
				<span class="relative flex w-full items-center">
					<Search class="pointer-events-none absolute left-3 h-4 w-4 fm-muted" aria-hidden="true" />
					<input v-model.trim="search" type="search" class="fm-input fm-input-icon fm-tap" placeholder="Filter batch, item or lot" />
				</span>
			</label>
		</div>

		<StateBlock
			:required-roles="SCREEN_ROLES.quality"
			:loading="loading && !rows.length"
			:error="error"
			:empty="!loading && !rows.length"
			loading-text="Loading queue…"
			empty-title="Nothing awaiting quality"
			empty-hint="Quarantined and held batches holding stock appear here."
			:icon="ShieldCheck"
			:on-retry="reload"
		>
			<div class="grid gap-4 xl:grid-cols-[1.25fr_1fr]">
				<!-- Master -->
				<div class="fm-card overflow-hidden">
					<div class="flex flex-wrap items-start justify-between gap-2 p-4 pb-3">
						<div>
							<h2 class="font-bold">Batches awaiting review</h2>
							<p class="mt-0.5 text-sm fm-muted">Longest waiting first. Select a batch to review.</p>
						</div>
						<span class="fm-chip fm-chip-soft">{{ visibleRows.length }} shown</span>
					</div>

					<p v-if="!visibleRows.length" class="px-4 pb-4 text-sm fm-muted">
						No batch on this page matches “{{ search }}”.
					</p>

					<div v-else class="overflow-x-auto">
						<table class="fm-table">
							<caption class="sr-only">Batches awaiting a quality decision</caption>
							<thead>
								<tr>
									<th scope="col">Batch</th>
									<th scope="col">Item / supplier lot</th>
									<th scope="col">Status</th>
									<th scope="col" class="text-right">Quantity</th>
								</tr>
							</thead>
							<tbody>
								<tr
									v-for="row in visibleRows"
									:key="row.name"
									class="cursor-pointer"
									:style="selected === row.name
										? { background: 'var(--fm-soft)', boxShadow: 'inset 3px 0 0 var(--fm-primary)' }
										: {}"
									:aria-selected="selected === row.name"
									tabindex="0"
									@click="open(row)"
									@keydown.enter.prevent="open(row)"
									@keydown.space.prevent="open(row)"
								>
									<td class="fm-id font-semibold" :style="{ color: 'var(--fm-primary)' }">{{ row.name }}</td>
									<td>
										<span class="block font-medium">{{ row.item_name || row.item }}</span>
										<span class="fm-num block text-xs fm-muted">{{ row.fm_supplier_lot_no || '—' }}</span>
									</td>
									<td><StatusChip :status="row.fm_quality_status" /></td>
									<td class="text-right">
										<span class="fm-num font-semibold">{{ fmt(row.qty) }}</span>
										<span v-if="row.stock_uom" class="ml-1 text-xs fm-muted">{{ row.stock_uom }}</span>
									</td>
								</tr>
							</tbody>
						</table>
					</div>

					<div class="flex flex-wrap items-center justify-between gap-2 border-t p-3 text-xs" :style="{ borderColor: 'var(--fm-border)' }">
						<span class="fm-muted">Company stock only · page {{ pageStart / PAGE_SIZE + 1 }}</span>
						<span class="flex gap-2">
							<button type="button" class="fm-btn-ghost fm-tap px-3" :disabled="pageStart === 0 || loading" @click="changePage(-PAGE_SIZE)">Previous</button>
							<button type="button" class="fm-btn-ghost fm-tap px-3" :disabled="rows.length < PAGE_SIZE || loading" @click="changePage(PAGE_SIZE)">Next</button>
						</span>
					</div>
				</div>

				<!-- Detail -->
				<div>
					<div v-if="!selected" class="fm-card grid place-items-center p-10 text-center">
						<div>
							<ShieldCheck class="mx-auto h-7 w-7 fm-muted" aria-hidden="true" />
							<p class="mt-2 text-sm font-semibold">Select a batch</p>
							<p class="mt-1 text-sm fm-muted">Its inspections, history and decision form appear here.</p>
						</div>
					</div>

					<StateBlock v-else :loading="contextLoading" :error="contextError" loading-text="Loading batch…" :required-roles="SCREEN_ROLES.quality">
						<div v-if="context" class="fm-card p-5">
							<div class="flex items-start gap-3">
								<span class="grid h-10 w-10 shrink-0 place-items-center rounded-xl" :style="{ background: 'var(--fm-soft)', color: 'var(--fm-primary)' }" aria-hidden="true">
									<Boxes class="h-5 w-5" />
								</span>
								<div class="min-w-0 flex-1">
									<h2 class="text-lg font-bold">{{ context.batch.item_name || context.batch.item }}</h2>
									<p class="mt-0.5 flex flex-wrap items-center gap-2">
										<span class="fm-num text-sm fm-muted">{{ context.batch.name }}</span>
										<StatusChip :status="context.batch.quality_status" />
									</p>
								</div>
							</div>

							<dl class="mt-4 grid grid-cols-2 gap-4">
								<div>
									<dt class="fm-label">Stock quantity</dt>
									<dd class="fm-num mt-0.5 font-semibold">{{ fmt(context.batch.qty ?? selectedRow?.qty) }} {{ context.batch.stock_uom || '' }}</dd>
								</div>
								<div>
									<dt class="fm-label">Expiry</dt>
									<dd class="fm-num mt-0.5 font-semibold">{{ context.batch.expiry_date || '—' }}</dd>
								</div>
								<div>
									<dt class="fm-label">Supplier</dt>
									<dd class="mt-0.5 font-semibold">{{ context.batch.supplier || '—' }}</dd>
								</div>
								<div>
									<dt class="fm-label">Supplier lot</dt>
									<dd class="fm-num mt-0.5 font-semibold">{{ context.batch.supplier_lot_no || '—' }}</dd>
								</div>
								<div v-if="context.batch.remaining_shelf_life_percent !== null && context.batch.remaining_shelf_life_percent !== undefined" class="col-span-2">
									<dt class="fm-label">Shelf life remaining</dt>
									<dd class="mt-1 flex items-center gap-2">
										<span class="h-2 w-full max-w-[10rem] overflow-hidden rounded-full" :style="{ background: 'var(--fm-border)' }">
											<span class="block h-full rounded-full" :style="{ width: `${Math.min(100, context.batch.remaining_shelf_life_percent)}%`, background: 'var(--fm-primary)' }" />
										</span>
										<span class="fm-num text-sm font-semibold">{{ fmt(context.batch.remaining_shelf_life_percent) }}%</span>
									</dd>
								</div>
							</dl>

							<form class="mt-5 border-t pt-4" :style="{ borderColor: 'var(--fm-border)' }" @submit.prevent="submit">
								<label class="block">
									<span class="fm-label">Matching inspection</span>
									<select v-model="form.inspection" class="fm-input fm-tap mt-1">
										<option v-for="option in inspectionOptions" :key="option.value" :value="option.value">
											{{ option.label }}
										</option>
									</select>
									<span class="mt-1 block text-xs fm-muted">
										Release requires the accepted inspection for this exact item and batch when company policy requires it.
									</span>
								</label>

								<div v-if="context.history.length" class="mt-4">
									<p class="fm-label">Decision history</p>
									<ul class="mt-1.5 space-y-2">
										<li v-for="item in context.history" :key="item.name" class="flex gap-2 text-sm">
											<span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" :style="{ background: 'var(--fm-primary)' }" aria-hidden="true" />
											<span>
												<span class="block font-semibold">{{ item.decision }} recorded</span>
												<span class="block text-xs fm-muted">{{ item.posting_datetime }} · {{ item.decided_by }}</span>
												<span v-if="item.reason" class="block text-xs fm-muted">{{ item.reason }}</span>
											</span>
										</li>
									</ul>
								</div>

								<fieldset class="mt-4">
									<legend class="fm-label mb-1.5">Decision</legend>
									<div class="flex flex-wrap gap-2">
										<label
											v-for="option in decisions"
											:key="option"
											class="fm-tap flex cursor-pointer items-center gap-2 rounded-lg px-3 text-sm font-semibold"
											:style="form.decision === option
												? { background: 'var(--fm-primary)', color: '#fff', border: '1px solid var(--fm-primary)' }
												: { border: '1px solid var(--fm-border)' }"
										>
											<input v-model="form.decision" type="radio" :value="option" class="sr-only" />
											<component :is="decisionIcon(option)" class="h-4 w-4" aria-hidden="true" />
											{{ option }}
										</label>
									</div>
								</fieldset>

								<label class="mt-4 block">
									<span class="fm-label">Decision notes</span>
									<textarea
										v-model="form.reason"
										rows="3"
										:required="needsReason"
										class="fm-input mt-1"
										placeholder="Explain the decision or required follow-up."
									/>
									<span class="mt-1 block text-xs fm-muted">
										A reason is mandatory for Hold or Reject.
									</span>
								</label>

								<p v-if="submitError" role="alert" class="mt-4 whitespace-pre-line rounded-xl p-3 text-sm" :style="{ background: 'var(--fm-bad-bg)', color: 'var(--fm-bad)' }">
									{{ errorMessage(submitError) }}
								</p>

								<p v-if="submitResult" role="status" class="mt-4 rounded-xl p-3 text-sm" :style="{ background: 'var(--fm-good-bg)', color: 'var(--fm-good)' }">
									Recorded {{ submitResult.name }} — batch is now {{ submitResult.quality_status }}.
								</p>

								<button
									type="submit"
									class="fm-btn-primary fm-tap mt-4 flex w-full items-center justify-center gap-2 px-4 text-sm"
									:disabled="!form.decision || submitting || Boolean(submitResult)"
								>
									<Check class="h-4 w-4" aria-hidden="true" />
									{{ submitting ? 'Recording…' : submitResult ? 'Recorded' : 'Record decision' }}
								</button>
							</form>
						</div>
					</StateBlock>
				</div>
			</div>
		</StateBlock>
	</section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
	Boxes, Check, CheckCircle, ClipboardCheck, PauseCircle, RefreshCw, Search, ShieldCheck, XOctagon,
} from 'lucide-vue-next'

import KpiCard from '@/components/KpiCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import { SCREEN_ROLES } from '@/data/access'
import StatusChip from '@/components/StatusChip.vue'
import { dashboard, errorMessage, quality } from '@/data/api'

const props = defineProps({ company: { type: String, required: true } })
const emit = defineEmits(['counts-changed'])

const PAGE_SIZE = 100
const decisions = ['Release', 'Hold', 'Reject']

const statusFilters = [
	{ value: '', label: 'All batches' },
	{ value: 'Quarantine', label: 'Quarantine' },
	{ value: 'Hold', label: 'Hold' },
]

const tabs = [
	{ name: 'Quality', label: 'Workspace', icon: ShieldCheck },
	{ name: 'QualityInsights', label: 'Insights', icon: ClipboardCheck },
]

const rows = ref([])
const pageStart = ref(0)
const status = ref('')
const search = ref('')
const loading = ref(false)
const error = ref(null)

const counts = ref({ quarantine: 0, hold: 0, total: 0 })
const releasedInPeriod = ref(null)

const selected = ref(null)
const context = ref(null)
const contextLoading = ref(false)
const contextError = ref(null)

const submitting = ref(false)
const submitError = ref(null)
const submitResult = ref(null)
const form = reactive({ decision: '', reason: '', inspection: '' })

const fmt = (value) => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })

const selectedRow = computed(() => rows.value.find((row) => row.name === selected.value))
const needsReason = computed(() => form.decision && form.decision !== 'Release')

/* Search filters the loaded page only - the endpoint paginates and has no
   search parameter, and the footer says which page is on screen. */
const visibleRows = computed(() => {
	const term = search.value.toLowerCase()
	if (!term) return rows.value
	return rows.value.filter((row) =>
		[row.name, row.item_name, row.item, row.fm_supplier_lot_no]
			.filter(Boolean)
			.some((value) => String(value).toLowerCase().includes(term))
	)
})

const inspectionOptions = computed(() => [
	{ label: 'None', value: '' },
	...(context.value?.inspections || []).map((item) => ({
		label: `${item.name} · ${item.status}`,
		value: item.name,
	})),
])

function decisionIcon(option) {
	return { Release: CheckCircle, Hold: PauseCircle, Reject: XOctagon }[option]
}

async function load() {
	loading.value = true
	error.value = null
	try {
		rows.value = await quality.queue({
			company: props.company,
			start: pageStart.value,
			limit: PAGE_SIZE,
			status: status.value || undefined,
		})
		if (rows.value.length && !rows.value.some((row) => row.name === selected.value)) {
			await open(rows.value[0])
		}
	} catch (err) {
		error.value = err
	} finally {
		loading.value = false
	}
}

async function loadCounts() {
	try {
		counts.value = await quality.counts({ company: props.company })
	} catch {
		counts.value = { quarantine: 0, hold: 0, total: 0 }
	}

	try {
		const data = await dashboard.get({ company: props.company, days: 30 })
		releasedInPeriod.value = data?.kpis?.batches_released ?? null
	} catch {
		// An unavailable figure stays unknown rather than becoming a zero.
		releasedInPeriod.value = null
	}
}

async function reload() {
	await Promise.all([load(), loadCounts()])
}

async function setStatus(value) {
	status.value = value
	pageStart.value = 0
	await load()
}

async function changePage(delta) {
	pageStart.value = Math.max(0, pageStart.value + delta)
	await load()
}

async function open(row) {
	selected.value = row.name
	context.value = null
	contextError.value = null
	contextLoading.value = true
	submitError.value = null
	submitResult.value = null
	form.decision = ''
	form.reason = ''
	form.inspection = ''

	try {
		context.value = await quality.batchContext({ batch: row.name })
	} catch (err) {
		contextError.value = err
	} finally {
		contextLoading.value = false
	}
}

async function submit() {
	// A confirmed decision must not be recorded twice by a second click.
	if (submitting.value || submitResult.value) return

	submitting.value = true
	submitError.value = null

	try {
		submitResult.value = await quality.recordDecision({
			batch: context.value.batch.name,
			company: props.company,
			decision: form.decision,
			reason: form.reason || null,
			quality_inspection: form.inspection || null,
		})
		await reload()
		emit('counts-changed')
	} catch (err) {
		submitError.value = err
	} finally {
		submitting.value = false
	}
}

onMounted(reload)
</script>

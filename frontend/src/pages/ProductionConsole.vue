<template>
	<section>
		<PageHeader
			eyebrow="Production workspace"
			title="Production"
			subtitle="Released ingredients. Clear work orders. Confident completions."
			:tabs="tabs"
		>
			<template #actions>
				<button type="button" class="fm-btn-ghost fm-tap flex items-center gap-2 px-3 text-sm" @click="load">
					<RefreshCw class="h-4 w-4" :class="loading ? 'animate-spin motion-reduce:animate-none' : ''" aria-hidden="true" />
					Refresh
				</button>
			</template>
		</PageHeader>

		<!-- One filter row above everything it scopes, and outside the state
		     block: an empty result must still leave you the means to change it. -->
		<div class="mb-4 flex flex-wrap items-center gap-2">
			<div class="flex flex-wrap gap-1.5" role="group" aria-label="Status">
				<button
					v-for="option in STATUSES"
					:key="option.value || 'all'"
					type="button"
					class="fm-tap rounded-xl px-3 text-sm font-medium transition-colors motion-reduce:transition-none"
					:class="option.value === status ? 'fm-btn-primary' : 'fm-btn-ghost'"
					:aria-pressed="option.value === status"
					@click="setStatus(option.value)"
				>
					{{ option.label }}
				</button>
			</div>

			<label class="ml-auto w-full sm:w-72">
				<span class="sr-only">Search work orders</span>
				<span class="relative flex w-full items-center">
					<Search class="pointer-events-none absolute left-3 h-4 w-4 fm-muted" aria-hidden="true" />
					<input
						v-model="search"
						type="search"
						class="fm-input fm-input-icon fm-tap w-full"
						placeholder="Work order or product"
						@input="onSearch"
					/>
				</span>
			</label>
		</div>

		<StateBlock
			:required-roles="SCREEN_ROLES.production"
			:loading="loading && !rows.length"
			:error="error"
			:empty="!loading && !rows.length"
			loading-text="Loading production queue…"
			:empty-title="search ? 'Nothing matches that search' : 'No open production runs'"
			:empty-hint="search ? 'Try a work order number or a product name.' : 'Submitted Work Orders for this company appear here.'"
			:icon="Factory"
			:on-retry="load"
		>
			<div class="grid gap-4 lg:grid-cols-[20rem_1fr] xl:grid-cols-[22rem_1fr]">
				<!-- Master: horizontally scrollable on a phone, a column on desktop. -->
				<div>
					<div class="mb-2 flex items-baseline justify-between">
						<h2 class="text-sm font-bold">Open work orders</h2>
						<span class="fm-chip fm-chip-soft">{{ rows.length }} shown</span>
					</div>

					<ul class="flex gap-3 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible lg:pb-0">
						<li v-for="row in rows" :key="row.name" class="w-[17rem] shrink-0 lg:w-auto">
							<button
								type="button"
								class="fm-card w-full p-4 text-left transition-colors motion-reduce:transition-none"
								:style="selected === row.name
									? { borderColor: 'var(--fm-primary)', boxShadow: '0 0 0 1px var(--fm-primary)' }
									: {}"
								:aria-current="selected === row.name ? 'true' : undefined"
								@click="open(row)"
							>
								<div class="flex items-start justify-between gap-2">
									<span class="fm-num text-xs fm-muted">{{ row.name }}</span>
									<span class="fm-chip fm-chip-soft">{{ row.status }}</span>
								</div>
								<p class="mt-1.5 font-bold">{{ row.item_name || row.production_item }}</p>
								<p class="mt-0.5 text-xs fm-muted">
									<span class="fm-num">{{ fmt(row.qty) }}</span> {{ row.stock_uom }} planned
								</p>

								<div class="mt-3 border-t pt-2" :style="{ borderColor: 'var(--fm-border)' }">
									<div class="flex items-center justify-between text-xs">
										<span class="fm-muted">Remaining</span>
										<span class="fm-num font-semibold">{{ fmt(row.pending_qty) }} {{ row.stock_uom }}</span>
									</div>
									<!-- How far through the run is. The bar showed it; only a
									     figure says whether it is 4% or 40%. -->
									<div class="mt-1 flex items-center justify-between text-[11px] fm-muted">
										<span>{{ row.status }}</span>
										<span class="fm-num">{{ progress(row) }}% complete</span>
									</div>
									<!-- Readiness belongs where the run is picked, not only
									     after opening it. -->
									<p
										v-if="row.short_items"
										class="mt-1.5 flex items-center gap-1 text-[11px] font-medium"
										:style="{ color: 'var(--fm-bad)' }"
									>
										<AlertTriangle class="h-3 w-3 shrink-0" aria-hidden="true" />
										Short of {{ row.short_items }}
										{{ row.short_items === 1 ? 'ingredient' : 'ingredients' }}
									</p>
									<div class="mt-1.5 h-1.5 w-full overflow-hidden rounded-full" :style="{ background: 'var(--fm-border)' }">
										<div class="h-full rounded-full" :style="{ width: `${progress(row)}%`, background: 'var(--fm-primary)' }" />
									</div>
								</div>
							</button>
						</li>
					</ul>
				</div>

				<!-- Detail -->
				<div v-if="selected" class="space-y-4">
					<StateBlock :loading="detailLoading" :error="detailError" loading-text="Loading run…" :required-roles="SCREEN_ROLES.production">
						<div v-if="detail" class="space-y-4">
							<div class="fm-card p-5">
								<div class="flex flex-wrap items-start justify-between gap-3">
									<div>
										<p class="fm-num text-xs fm-muted">{{ detail.work_order.name }}</p>
										<h2 class="mt-0.5 text-xl font-extrabold">
											{{ detail.work_order.item_name || detail.work_order.production_item }}
										</h2>
										<p class="mt-0.5 text-xs fm-muted">
											{{ detail.work_order.status }} · BOM {{ detail.work_order.bom_no }}
										</p>
									</div>
									<!-- A pending yield is not a good yield: it stays neutral until
									     there is a figure to report. -->
									<span class="fm-chip" :class="yieldChipClass">
										<component :is="yieldChipIcon" class="h-3.5 w-3.5" aria-hidden="true" />
										{{ detail.work_order.yield_percent ? `${fmt(detail.work_order.yield_percent)}% yield` : 'Yield pending' }}
									</span>
								</div>

								<dl class="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
									<div>
										<dt class="fm-label">Planned</dt>
										<dd class="fm-num mt-0.5 text-xl font-bold">{{ fmt(detail.work_order.qty) }} <span class="text-xs font-normal fm-muted">{{ unit }}</span></dd>
									</div>
									<div>
										<dt class="fm-label">Produced</dt>
										<dd class="fm-num mt-0.5 text-xl font-bold">{{ fmt(detail.work_order.produced_qty) }} <span class="text-xs font-normal fm-muted">{{ unit }}</span></dd>
									</div>
									<div>
										<dt class="fm-label">Remaining</dt>
										<dd class="fm-num mt-0.5 text-xl font-bold" :style="{ color: 'var(--fm-primary)' }">
											{{ fmt(remaining) }} <span class="text-xs font-normal fm-muted">{{ unit }}</span>
										</dd>
									</div>
								</dl>
							</div>

							<div class="fm-card overflow-hidden">
								<div class="flex flex-wrap items-start justify-between gap-2 p-5 pb-3">
									<div>
										<h3 class="font-bold">Ingredients &amp; released lots</h3>
										<p class="mt-0.5 text-sm fm-muted">Available stock, earliest expiry first.</p>
									</div>
									<span class="fm-chip fm-chip-good">
										<ShieldCheck class="h-3.5 w-3.5" aria-hidden="true" />
										Released stock only
									</span>
									<!-- A blank quantity is withheld, not zero. Saying which
									     keeps an em dash from reading as a bug. -->
									<span v-if="formulaWithheld" class="fm-chip fm-chip-warn">
										<Lock class="h-3.5 w-3.5" aria-hidden="true" />
										Quantities need recipe access
									</span>
								</div>

								<div class="overflow-x-auto">
									<table class="fm-table">
										<caption class="sr-only">Required ingredients with released lots</caption>
										<thead>
											<tr>
												<th scope="col">Ingredient</th>
												<th scope="col">Required</th>
												<th scope="col">Still needed</th>
												<th scope="col">Consumed</th>
												<th scope="col">Released lot</th>
												<th scope="col">Available</th>
												<th scope="col">Expiry</th>
											</tr>
										</thead>
										<tbody>
											<tr v-for="line in detail.ingredients" :key="line.item_code">
												<td class="font-medium align-top">{{ line.item_name || line.item_code }}</td>
												<td class="fm-num align-top">{{ qty(line.required_qty, line.stock_uom) }}</td>
												<td class="align-top">
													<span class="fm-num">{{ qty(line.outstanding_qty, line.stock_uom) }}</span>
													<span
														v-if="line.short"
														class="mt-0.5 flex items-center gap-1 text-[11px] font-medium"
														:style="{ color: 'var(--fm-bad)' }"
													>
														<AlertTriangle class="h-3 w-3 shrink-0" aria-hidden="true" />
														{{ line.short_qty === null ? 'short of stock' : `short ${fmt(line.short_qty)} ${line.stock_uom}` }}
													</span>
												</td>
												<td class="fm-num fm-muted align-top">{{ qty(line.consumed_qty, line.stock_uom) }}</td>
												<td class="align-top">
													<span v-if="earliest(line)" class="fm-num font-semibold">{{ earliest(line).batch_no }}</span>
													<span v-else class="fm-chip fm-chip-warn">
														<AlertTriangle class="h-3.5 w-3.5" aria-hidden="true" />
														No released stock
													</span>
													<span v-if="line.available_lots.length > 1" class="mt-0.5 block text-xs fm-muted">
														+{{ line.available_lots.length - 1 }} more released lot(s)
													</span>
												</td>
												<td class="fm-num align-top">
													{{ earliest(line) ? `${fmt(earliest(line).available_qty)} ${line.stock_uom}` : '—' }}
												</td>
												<td class="fm-num align-top">
													{{ earliest(line)?.expiry_date || '—' }}
												</td>
											</tr>
										</tbody>
									</table>
								</div>

								<p class="flex items-center gap-2 border-t px-5 py-3 text-xs fm-muted" :style="{ borderColor: 'var(--fm-border)' }">
									<ShieldCheck class="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
									Only eligible released lots can be consumed. The server enforces this on submit.
								</p>

								<p
									v-if="formulaWithheld"
									class="flex items-center gap-2 border-t px-5 py-3 text-xs fm-muted"
									:style="{ borderColor: 'var(--fm-border)' }"
								>
									<Lock class="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
									Ingredient quantities are part of the confidential formula, so this
									account sees which ingredients a run needs and whether they are in
									stock, but not how much of each.
								</p>
							</div>

							<form class="fm-card p-5" @submit.prevent="askToFinish">
								<h3 class="font-bold">Finish this run</h3>
								<p class="mt-0.5 text-sm fm-muted">Record actual output and non-recoverable process loss.</p>

								<div class="mt-4 grid gap-4 sm:grid-cols-2">
									<label class="block">
										<span class="fm-label">Good output</span>
										<span class="mt-1 flex items-center gap-2">
											<input v-model="form.qty" type="number" step="any" min="0" required class="fm-input fm-tap" />
											<span class="text-sm fm-muted">{{ unit }}</span>
										</span>
									</label>
									<label class="block">
										<span class="fm-label">Process loss</span>
										<span class="mt-1 flex items-center gap-2">
											<input v-model="form.processLoss" type="number" step="any" min="0" class="fm-input fm-tap" />
											<span class="text-sm fm-muted">{{ unit }}</span>
										</span>
									</label>
								</div>

								<label class="mt-4 block">
									<span class="fm-label">Output batch reference (optional)</span>
									<input v-model="form.finishedBatch" type="text" class="fm-input fm-tap mt-1" placeholder="Automatic batch naming" />
									<span class="mt-1 block text-xs fm-muted">Leave blank to let ERPNext name the output batch.</span>
								</label>

								<p v-if="finishError" role="alert" class="mt-4 rounded-xl p-3 text-sm" :style="{ background: 'var(--fm-bad-bg)', color: 'var(--fm-bad)' }">
									{{ errorMessage(finishError) }}
								</p>

								<p v-if="finishResult" role="status" class="mt-4 rounded-xl p-3 text-sm" :style="{ background: 'var(--fm-good-bg)', color: 'var(--fm-good)' }">
									Posted {{ finishResult.stock_entry }} — yield {{ fmt(finishResult.yield_percent) }}%<template v-if="finishResult.yield_flagged">, flagged as outside tolerance</template>.
								</p>

								<div class="mt-4 flex flex-wrap items-center justify-between gap-3 border-t pt-4" :style="{ borderColor: 'var(--fm-border)' }">
									<p v-if="blockedReason" class="flex items-center gap-1.5 text-xs font-medium" :style="{ color: 'var(--fm-bad)' }">
										<AlertTriangle class="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
										{{ blockedReason }}
									</p>
									<p v-else class="text-xs fm-muted">
										Review the quantities before completing this Work Order.
									</p>
									<button
										type="submit"
										class="fm-btn-primary fm-tap flex items-center gap-2 px-4 text-sm"
										:disabled="finishing || Boolean(finishResult) || Boolean(blockedReason)"
										:title="blockedReason || undefined"
									>
										<Check class="h-4 w-4" aria-hidden="true" />
										{{ finishing ? 'Posting…' : finishResult ? 'Completed' : actionLabel }}
									</button>
								</div>
							</form>
						</div>
					</StateBlock>
				</div>

				<div v-else class="fm-card grid place-items-center p-10 text-center">
					<div>
						<Factory class="mx-auto h-7 w-7 fm-muted" aria-hidden="true" />
						<p class="mt-2 text-sm font-semibold">Select a work order</p>
						<p class="mt-1 text-sm fm-muted">Its ingredients and completion form appear here.</p>
					</div>
				</div>
			</div>
		</StateBlock>

		<!-- Completing a run posts a Stock Entry and consumes released lots.
		     That is not undone by a second click. -->
		<ConfirmDialog
			:open="confirming"
			title="Complete this run?"
			body="This posts a Stock Entry, consumes the released lots above and creates the output batch. It cannot be undone from here."
			:details="confirmDetails"
			confirm-label="Post and complete"
			@confirm="confirmFinish"
			@cancel="confirming = false"
		/>
	</section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { AlertTriangle, Check, CheckCircle, Clock, Factory, LineChart, Lock, RefreshCw, Search, ShieldCheck } from 'lucide-vue-next'

import PageHeader from '@/components/PageHeader.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import StateBlock from '@/components/StateBlock.vue'
import { SCREEN_ROLES } from '@/data/access'
import { debounce } from '@/utils/debounce'
import { errorMessage, production } from '@/data/api'

const props = defineProps({ company: { type: String, required: true } })
const emit = defineEmits(['counts-changed'])

const rows = ref([])
const loading = ref(false)
const error = ref(null)

const selected = ref(null)
const detail = ref(null)
const detailLoading = ref(false)
const detailError = ref(null)

const finishing = ref(false)
const finishError = ref(null)
const finishResult = ref(null)
const STATUSES = [
	{ value: '', label: 'All open' },
	{ value: 'Not Started', label: 'Not started' },
	{ value: 'In Process', label: 'In process' },
]

const search = ref('')
const status = ref('')

/* Debounced: a request per keystroke answers one question five times, and the
   answers can arrive out of order. */
const onSearch = debounce(() => load(), 300)

function setStatus(value) {
	status.value = value
	load()
}

/* The stage action comes from the server: a button that disagrees with the rule
   behind it is worse than no button. */
const confirming = ref(false)

/* The dialog repeats what is about to be posted. A confirmation that only asks
   "are you sure" adds a click without adding certainty. */
const confirmDetails = computed(() => [
	{ label: 'Work order', value: selected.value || '—' },
	{ label: 'Good output', value: `${form.qty || 0} ${unit.value}` },
	{ label: 'Process loss', value: `${form.processLoss || 0} ${unit.value}` },
])

function askToFinish() {
	if (finishing.value || finishResult.value || blockedReason.value) return
	confirming.value = true
}

async function confirmFinish() {
	confirming.value = false
	await finish()
}

const nextAction = computed(() => detail.value?.next_action || null)
const actionLabel = computed(() => nextAction.value?.label || 'Complete run')
const blockedReason = computed(() =>
	nextAction.value && !nextAction.value.enabled ? nextAction.value.reason : null
)

const form = reactive({ qty: '', processLoss: '', finishedBatch: '' })

const tabs = [
	{ name: 'Production', label: 'Workspace', icon: Factory },
	{ name: 'ProductionInsights', label: 'Insights', icon: LineChart },
]

const fmt = (value) => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 3 })
/* A withheld figure is not a zero. The server blanks the ingredient quantities
   for an account that may not read the recipe, and printing 0 for that would be
   a wrong number rather than a missing one. */
const qty = (value, uom) =>
	value === null || value === undefined ? '—' : `${fmt(value)} ${uom || ''}`.trim()
const formulaWithheld = computed(() => detail.value?.shows_ingredient_detail === false)
const unit = computed(() => detail.value?.work_order?.stock_uom || '')
/* The earliest-expiring released lot fills the columns; the rest are counted,
   so Available and Expiry always carry a real value or an em dash. */
function earliest(line) {
	return line.available_lots?.[0] || null
}

const yieldChipClass = computed(() => {
	const wo = detail.value?.work_order
	if (!wo?.yield_percent) return 'fm-chip-soft'
	return wo.yield_flagged ? 'fm-chip-bad' : 'fm-chip-good'
})

const yieldChipIcon = computed(() => {
	const wo = detail.value?.work_order
	if (!wo?.yield_percent) return Clock
	return wo.yield_flagged ? AlertTriangle : CheckCircle
})

const remaining = computed(() => {
	const wo = detail.value?.work_order
	if (!wo) return 0
	return Number(wo.qty || 0) - Number(wo.produced_qty || 0) - Number(wo.process_loss_qty || 0)
})

function progress(row) {
	const planned = Number(row.qty || 0)
	if (!planned) return 0
	const done = Number(row.produced_qty || 0) + Number(row.process_loss_qty || 0)
	return Math.round(Math.min(100, Math.max(0, (done / planned) * 100)))
}

async function load() {
	loading.value = true
	error.value = null
	try {
		rows.value = await production.queue({
			company: props.company,
			search: search.value || undefined,
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

async function open(row) {
	selected.value = row.name
	detail.value = null
	detailError.value = null
	detailLoading.value = true
	finishError.value = null
	finishResult.value = null

	try {
		detail.value = await production.detail({ work_order: row.name })
		form.qty = String(row.pending_qty || '')
		form.processLoss = ''
		form.finishedBatch = ''
	} catch (err) {
		detailError.value = err
	} finally {
		detailLoading.value = false
	}
}

async function finish() {
	// A confirmed success must not be posted twice by an impatient second click.
	if (finishing.value || finishResult.value) return

	finishing.value = true
	finishError.value = null

	try {
		finishResult.value = await production.finishRun({
			work_order: detail.value.work_order.name,
			qty: form.qty,
			process_loss_qty: form.processLoss || 0,
			finished_batch: form.finishedBatch || null,
		})
		await load()
		emit('counts-changed')
	} catch (err) {
		finishError.value = err
	} finally {
		finishing.value = false
	}
}

onMounted(load)
</script>

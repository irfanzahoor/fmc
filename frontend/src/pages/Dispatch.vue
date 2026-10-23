<template>
	<section>
		<PageHeader
			eyebrow="Dispatch workspace"
			title="Dispatch"
			subtitle="The right stock, in the right order, for every customer."
		>
			<template #actions>
				<button type="button" class="fm-btn-ghost fm-tap flex items-center gap-2 px-3 text-sm" @click="load">
					<RefreshCw class="h-4 w-4" :class="loading ? 'animate-spin motion-reduce:animate-none' : ''" aria-hidden="true" />
					Refresh
				</button>
			</template>
		</PageHeader>

		<StateBlock
			:required-roles="SCREEN_ROLES.dispatch"
			:loading="loading && !orders.length"
			:error="error"
			:empty="!loading && !orders.length"
			loading-text="Loading sales orders…"
			empty-title="Nothing awaiting dispatch"
			empty-hint="Submitted sales orders with quantity outstanding appear here."
			:icon="Truck"
			:on-retry="load"
		>
			<!-- Order selector -->
			<ul class="mb-4 flex gap-3 overflow-x-auto pb-1">
				<li v-for="order in orders" :key="order.name" class="w-[16rem] shrink-0">
					<button
						type="button"
						class="fm-card w-full p-4 text-left"
						:style="selected === order.name ? { borderColor: 'var(--fm-primary)', boxShadow: '0 0 0 1px var(--fm-primary)' } : {}"
						:aria-current="selected === order.name ? 'true' : undefined"
						@click="open(order)"
					>
						<p class="font-bold">{{ order.customer_name || order.customer }}</p>
						<p class="fm-num mt-0.5 text-xs fm-muted">{{ order.name }} · due {{ order.delivery_date || '—' }}</p>
						<p class="fm-num mt-2 text-xs fm-muted">{{ fmt(order.per_delivered) }}% delivered</p>
					</button>
				</li>
			</ul>

			<StateBlock v-if="selected" :loading="pickLoading" :error="pickError" loading-text="Loading picklist…" :required-roles="SCREEN_ROLES.dispatch">
				<form v-if="picklist" class="space-y-4" @submit.prevent="submit">
					<!-- Context bar -->
					<div class="fm-card p-5">
						<dl class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
							<div>
								<dt class="fm-label">Sales order</dt>
								<dd class="fm-num mt-1 font-bold">{{ picklist.sales_order }}</dd>
								<dd class="text-xs fm-muted">{{ picklist.lines.length }} outstanding item line(s)</dd>
							</div>
							<div>
								<dt class="fm-label">Customer</dt>
								<dd class="mt-1 font-bold">{{ picklist.customer_name || picklist.customer }}</dd>
								<dd class="text-xs fm-muted">Finished goods delivery</dd>
							</div>
							<div>
								<dt class="fm-label">Delivery date</dt>
								<dd class="fm-num mt-1 font-bold">{{ selectedOrder?.delivery_date || '—' }}</dd>
								<dd class="text-xs fm-muted">Sales order commitment</dd>
							</div>
							<div>
								<dt class="fm-label">Warehouse</dt>
								<dd class="mt-1 font-bold">{{ picklist.lines[0]?.warehouse || '—' }}</dd>
								<dd class="text-xs fm-muted">Company dispatch stock</dd>
							</div>
						</dl>

						<div class="mt-4 flex flex-wrap items-center gap-2 border-t pt-3" :style="{ borderColor: 'var(--fm-border)' }">
							<span class="fm-chip fm-chip-soft">FEFO · {{ picklist.fefo_mode }}</span>
							<span v-if="picklist.min_remaining_shelf_life_percent" class="fm-chip fm-chip-soft">
								Minimum shelf life · {{ fmt(picklist.min_remaining_shelf_life_percent) }}%
							</span>
							<span class="ml-auto text-xs fm-muted">Policy checks remain authoritative on submit.</span>
						</div>
					</div>

					<!-- Sales UOM to stock UOM, always visible. -->
					<div class="fm-card p-5">
						<h2 class="font-bold">Sales quantity → stock quantity</h2>
						<p class="mt-0.5 text-sm fm-muted">Allocate in stock units, with the sales conversion shown.</p>

						<ul class="mt-4 grid gap-3 sm:grid-cols-2">
							<li v-for="line in picklist.lines" :key="`c${line.name}`" class="rounded-xl p-4" :style="{ background: 'var(--fm-canvas)' }">
								<p class="font-semibold">{{ line.item_name || line.item_code }}</p>
								<div class="mt-3 flex items-end justify-between gap-3 border-t pt-3" :style="{ borderColor: 'var(--fm-border)' }">
									<span class="text-xs fm-muted">
										<span class="fm-num font-semibold" :style="{ color: 'var(--fm-ink)' }">
											{{ fmt(line.ordered_qty - line.delivered_qty) }} {{ line.uom }}
										</span>
										outstanding
									</span>
									<span class="text-right">
										<span class="fm-num text-[22px] font-extrabold leading-none">{{ fmt(line.pending_qty) }}</span>
										<span class="ml-1 text-xs fm-muted">{{ line.stock_uom }} required</span>
									</span>
								</div>
							</li>
						</ul>
					</div>

					<!-- Scanner: Enter focuses a quantity field, it never posts. -->
					<div class="fm-card flex flex-wrap items-center gap-4 p-5">
						<span class="grid h-10 w-10 shrink-0 place-items-center rounded-xl" :style="{ background: 'var(--fm-soft)', color: 'var(--fm-primary)' }" aria-hidden="true">
							<ScanLine class="h-5 w-5" />
						</span>
						<span class="min-w-0">
							<span class="block font-semibold">Scan a batch</span>
							<span class="block text-xs fm-muted">Enter focuses the matching quantity field. It does not post the dispatch.</span>
						</span>
						<span class="ml-auto flex min-w-[16rem] flex-1 items-center gap-2">
							<label class="flex-1">
								<span class="sr-only">Batch ID</span>
								<input
									v-model.trim="scannedBatch"
									class="fm-input fm-tap fm-num"
									placeholder="Batch ID, then Enter"
									autocomplete="off"
									@keydown.enter.prevent="focusBatch"
								/>
							</label>
							<button type="button" class="fm-btn-ghost fm-tap px-4 text-sm" @click="focusBatch">Find</button>
						</span>
						<p v-if="scanMessage" role="status" class="w-full text-sm" :style="{ color: 'var(--fm-bad)' }">{{ scanMessage }}</p>
					</div>

					<!-- Allocations -->
					<div v-for="line in picklist.lines" :key="line.name" class="fm-card overflow-hidden">
						<div class="flex flex-wrap items-start justify-between gap-2 p-5 pb-3">
							<div>
								<h2 class="font-bold">{{ line.item_name || line.item_code }}</h2>
								<p class="mt-0.5 text-sm fm-muted">Released batches, ordered by earliest expiry.</p>
							</div>
							<span class="fm-chip fm-chip-soft">Stock UOM · {{ line.stock_uom }}</span>
						</div>

						<p v-if="line.shortfall" class="mx-5 mb-3 rounded-xl p-3 text-sm" :style="{ background: 'var(--fm-bad-bg)', color: 'var(--fm-bad)' }">
							Short by {{ fmt(line.shortfall) }} {{ line.stock_uom }} in {{ line.warehouse }}.
						</p>

						<p v-if="!line.candidates.length" class="px-5 pb-5 text-sm" :style="{ color: 'var(--fm-bad)' }">
							No dispatchable batch in {{ line.warehouse }}.
						</p>

						<div v-else class="overflow-x-auto">
							<table class="fm-table min-w-[46rem]">
								<caption class="sr-only">Available batches in first-expiry-first-out order</caption>
								<thead>
									<tr>
										<th scope="col">Batch / item</th>
										<th scope="col">Quality</th>
										<th scope="col">Expiry</th>
										<th scope="col">Shelf life</th>
										<th scope="col" class="text-right">Available</th>
										<th scope="col" class="text-right">Pick · {{ line.stock_uom }}</th>
									</tr>
								</thead>
								<tbody>
									<tr v-for="(batch, index) in line.candidates" :key="batch.batch_no" :style="batch.blocked_reason ? { background: 'var(--fm-canvas)' } : {}">
										<td>
											<span class="fm-num block font-semibold">{{ batch.batch_no }}</span>
											<span class="block text-xs fm-muted">{{ line.item_name || line.item_code }}</span>
											<span v-if="index === 0 && !batch.blocked_reason" class="mt-1 inline-block text-xs" :style="{ color: 'var(--fm-primary)' }">
												Earliest eligible expiry
											</span>
											<span v-if="batch.blocked_reason" class="mt-1 block text-xs" :style="{ color: 'var(--fm-bad)' }">
												Blocked · {{ batch.blocked_reason }}
											</span>
										</td>
										<td><StatusChip :status="batch.quality_status || 'Released'" /></td>
										<td class="fm-num">{{ batch.expiry_date || '—' }}</td>
										<td>
											<span v-if="batch.remaining_shelf_life_percent !== null && batch.remaining_shelf_life_percent !== undefined" class="flex items-center gap-2">
												<span class="fm-num text-xs font-semibold">{{ fmt(batch.remaining_shelf_life_percent) }}%</span>
												<span class="h-1.5 w-16 overflow-hidden rounded-full" :style="{ background: 'var(--fm-border)' }">
													<span class="block h-full rounded-full" :style="{ width: `${Math.min(100, batch.remaining_shelf_life_percent)}%`, background: 'var(--fm-primary)' }" />
												</span>
											</span>
											<span v-else class="text-xs fm-muted">—</span>
										</td>
										<td class="fm-num text-right">{{ fmt(batch.available_qty) }}</td>
										<td class="text-right">
											<input
												v-model="allocations[line.name][batch.batch_no]"
												:data-batch="batch.batch_no"
												type="number"
												step="any"
												min="0"
												:max="batch.available_qty"
												:disabled="Boolean(batch.blocked_reason)"
												class="fm-input fm-tap w-24 text-right disabled:opacity-60"
												:aria-label="`Pick quantity from batch ${batch.batch_no}`"
											/>
										</td>
									</tr>
								</tbody>
							</table>
						</div>

						<p class="flex flex-wrap items-center justify-between gap-2 border-t px-5 py-3 text-xs" :style="{ borderColor: 'var(--fm-border)' }">
							<span class="fm-muted">A suggestion does not reserve stock.</span>
							<span class="fm-num font-semibold">
								Allocated {{ fmt(allocatedFor(line)) }} of {{ fmt(line.pending_qty) }} {{ line.stock_uom }}
							</span>
						</p>
					</div>

					<p v-if="submitError" role="alert" class="whitespace-pre-line rounded-xl p-3 text-sm" :style="{ background: 'var(--fm-bad-bg)', color: 'var(--fm-bad)' }">
						{{ errorMessage(submitError) }}
					</p>

					<p v-if="submitResult" role="status" class="rounded-xl p-3 text-sm" :style="{ background: 'var(--fm-good-bg)', color: 'var(--fm-good)' }">
						Dispatched as {{ submitResult.delivery_note }}.
					</p>

					<div class="fm-card flex flex-wrap items-center justify-between gap-3 p-4">
						<p class="text-xs fm-muted">Shelf-life, FEFO and quality rules are enforced by the server on submit.</p>
						<button type="submit" class="fm-btn-primary fm-tap flex items-center gap-2 px-4 text-sm" :disabled="submitting || Boolean(submitResult)">
							<Check class="h-4 w-4" aria-hidden="true" />
							{{ submitting ? 'Posting…' : submitResult ? 'Dispatched' : 'Create delivery note' }}
						</button>
					</div>
				</form>
			</StateBlock>

			<div v-else class="fm-card grid place-items-center p-10 text-center">
				<div>
					<Truck class="mx-auto h-7 w-7 fm-muted" aria-hidden="true" />
					<p class="mt-2 text-sm font-semibold">Select a sales order</p>
					<p class="mt-1 text-sm fm-muted">Its picklist and FEFO suggestion appear here.</p>
				</div>
			</div>
		</StateBlock>
	</section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Check, RefreshCw, ScanLine, Truck } from 'lucide-vue-next'

import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import { SCREEN_ROLES } from '@/data/access'
import StatusChip from '@/components/StatusChip.vue'
import { dispatch, errorMessage } from '@/data/api'

const props = defineProps({ company: { type: String, required: true } })

const orders = ref([])
const loading = ref(false)
const error = ref(null)

const selected = ref(null)
const picklist = ref(null)
const pickLoading = ref(false)
const pickError = ref(null)
const allocations = reactive({})

const scannedBatch = ref('')
const scanMessage = ref('')

const submitting = ref(false)
const submitError = ref(null)
const submitResult = ref(null)

const fmt = (value) => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })

const selectedOrder = computed(() => orders.value.find((order) => order.name === selected.value))

function allocatedFor(line) {
	const picks = allocations[line.name] || {}
	return Object.values(picks).reduce((sum, qty) => sum + (Number(qty) || 0), 0)
}

/* Enter focuses the matching quantity field and never submits the form, so a
   scanner gun cannot post a dispatch by itself. */
function focusBatch() {
	const input = Array.from(document.querySelectorAll('input[data-batch]')).find(
		(element) => element.dataset.batch === scannedBatch.value && !element.disabled
	)

	if (input) {
		input.focus()
		input.select()
		scanMessage.value = ''
	} else {
		scanMessage.value = 'This batch is unavailable or blocked for this order.'
	}

	scannedBatch.value = ''
}

async function load() {
	loading.value = true
	error.value = null
	try {
		orders.value = await dispatch.openOrders({ company: props.company })
		if (orders.value.length && !orders.value.some((order) => order.name === selected.value)) {
			await open(orders.value[0])
		}
	} catch (err) {
		error.value = err
	} finally {
		loading.value = false
	}
}

async function open(order) {
	selected.value = order.name
	picklist.value = null
	pickError.value = null
	pickLoading.value = true
	submitError.value = null
	submitResult.value = null
	scanMessage.value = ''
	for (const key of Object.keys(allocations)) delete allocations[key]

	try {
		picklist.value = await dispatch.picklist({ sales_order: order.name })
		for (const line of picklist.value.lines) {
			allocations[line.name] = {}
			// Pre-fill the server's FEFO suggestion; the operator can override.
			for (const pick of line.suggestion) {
				allocations[line.name][pick.batch_no] = pick.qty
			}
			for (const batch of line.candidates) {
				if (!(batch.batch_no in allocations[line.name])) {
					allocations[line.name][batch.batch_no] = ''
				}
			}
		}
	} catch (err) {
		pickError.value = err
	} finally {
		pickLoading.value = false
	}
}

async function submit() {
	// A confirmed dispatch must not be posted twice by a second click.
	if (submitting.value || submitResult.value) return

	submitting.value = true
	submitError.value = null

	try {
		const lines = Object.entries(allocations).map(([name, picks]) => ({
			name,
			allocations: Object.entries(picks)
				.filter(([, qty]) => Number(qty) > 0)
				.map(([batch_no, qty]) => ({ batch_no, qty })),
		}))

		submitResult.value = await dispatch.createDeliveryNote({
			sales_order: picklist.value.sales_order,
			lines,
		})
		await load()
	} catch (err) {
		submitError.value = err
	} finally {
		submitting.value = false
	}
}

onMounted(load)
</script>

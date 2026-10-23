<template>
	<section aria-labelledby="fm-disp-heading">
		<PageHeader
			eyebrow="Dispatch"
			title="Dispatch"
			subtitle="Pick batches with a first-expiry-first-out suggestion."
		>
			<template #actions>
				<button type="button" class="fm-btn-ghost fm-tap flex items-center gap-2 px-3 text-sm" @click="load">
					<RefreshCw class="h-4 w-4" :class="loading ? 'animate-spin motion-reduce:animate-none' : ''" aria-hidden="true" />
					Refresh
				</button>
			</template>
		</PageHeader>

		<StateBlock
			:loading="loading"
			:error="error"
			:empty="!orders.length"
			loading-text="Loading sales orders…"
			empty-title="Nothing awaiting dispatch"
			empty-hint="Submitted sales orders with quantity outstanding will appear here."
			:icon="Truck"
			:on-retry="load"
		>
			<ul class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
				<li v-for="order in orders" :key="order.name" class="fm-card p-4">
					<p class="font-medium">{{ order.customer_name || order.customer }}</p>
					<p class="text-xs fm-muted">{{ order.name }} · due {{ order.delivery_date || '—' }}</p>
					<p class="mt-2 text-sm">{{ fmt(order.per_delivered) }}% delivered</p>
					<button type="button" class="fm-btn-primary fm-tap mt-3 w-full px-4 text-sm" @click="open(order)">Pick</button>
				</li>
			</ul>
		</StateBlock>

		<Dialog v-model="showPick" :options="{ title: picklist?.sales_order || 'Pick', size: '3xl' }">
			<template #body-content>
				<StateBlock :loading="pickLoading" :error="pickError" loading-text="Loading picklist…">
					<div v-if="picklist" class="space-y-4">
						<p class="rounded-xl p-3 text-sm" :style="{ background: 'var(--fm-canvas)' }">
							FEFO enforcement: <span class="font-medium">{{ picklist.fefo_mode }}</span>
							<template v-if="picklist.min_remaining_shelf_life_percent">
								· minimum shelf life {{ fmt(picklist.min_remaining_shelf_life_percent) }}%
							</template>
						</p>

						<form class="space-y-5" @submit.prevent="submit">
							<label class="block text-sm">Scan batch to focus its quantity
								<input v-model.trim="scannedBatch" class="fm-tap ml-2 rounded border p-2" @keydown.enter.prevent="focusBatch" placeholder="Batch ID + Enter" />
							</label>
							<p v-if="scanMessage" role="status" class="text-sm">{{ scanMessage }}</p>
							<fieldset v-for="line in picklist.lines" :key="line.name" class="fm-card p-3">
								<legend class="px-1 text-sm font-medium">
									{{ line.item_name || line.item_code }} — {{ fmt(line.pending_qty) }} {{ line.uom }} outstanding
								</legend>

								<p v-if="line.shortfall" class="mb-2 rounded-xl p-3 text-sm" :style="{ background: 'var(--fm-bad-bg)', color: 'var(--fm-bad)' }">
									Short by {{ fmt(line.shortfall) }} {{ line.stock_uom }} in {{ line.warehouse }}.
								</p>

								<p v-if="!line.candidates.length" class="text-sm" :style="{ color: 'var(--fm-bad)' }">
									No dispatchable batch in {{ line.warehouse }}.
								</p>

								<table v-else class="fm-table">
									<caption class="sr-only">Available batches in first-expiry-first-out order</caption>
									<thead>
										<tr >
											<th scope="col" >Batch</th>
											<th scope="col" >Available</th>
											<th scope="col" >Expiry</th>
											<th scope="col" >Shelf life</th>
											<th scope="col" class="py-1 font-medium">Pick qty (stock UOM)</th>
										</tr>
									</thead>
									<tbody>
										<tr
											v-for="(batch, index) in line.candidates"
											:key="batch.batch_no"
											
										>
											<td class="py-1 pr-3 font-mono text-xs">
												{{ batch.batch_no }}
												<!-- Earliest expiry is labelled in words, not by colour alone. -->
												<span v-if="index === 0" class="ml-1 rounded bg-blue-100 px-1 text-[11px] text-blue-900">
													FEFO
												</span>
											</td>
											<td class="py-1 pr-3">{{ fmt(batch.available_qty) }}</td>
											<td class="py-1 pr-3">{{ batch.expiry_date || '—' }}</td>
											<td class="py-1 pr-3">
												<span v-if="batch.remaining_shelf_life_percent !== null">
													{{ fmt(batch.remaining_shelf_life_percent) }}%
												</span>
												<span v-else class="fm-muted">—</span>
											</td>
											<td class="py-1">
												<input
													v-model="allocations[line.name][batch.batch_no]"
													:data-batch="batch.batch_no"
													type="number"
													step="any"
													min="0"
													:max="batch.available_qty"
													:disabled="Boolean(batch.blocked_reason)"
													class="fm-input fm-tap w-24 disabled:opacity-60"
													:aria-label="`Pick quantity from batch ${batch.batch_no}`"
												/>
												<span v-if="batch.blocked_reason" class="block text-xs" :style="{ color: 'var(--fm-bad)' }">
													{{ batch.blocked_reason }}
												</span>
											</td>
										</tr>
									</tbody>
								</table>
							</fieldset>

							<p v-if="submitError" role="alert" class="rounded-xl p-3 text-sm whitespace-pre-line" :style="{ background: 'var(--fm-bad-bg)', color: 'var(--fm-bad)' }">
								{{ errorMessage(submitError) }}
							</p>

							<p v-if="submitResult" role="status" class="rounded-xl p-3 text-sm" :style="{ background: 'var(--fm-good-bg)', color: 'var(--fm-good)' }">
								Dispatched as {{ submitResult.delivery_note }}.
							</p>

							<Button class="fm-tap" variant="solid" type="submit" :loading="submitting" :disabled="submitting || Boolean(submitResult)">
								Create delivery note
							</Button>
						</form>
					</div>
				</StateBlock>
			</template>
		</Dialog>
	</section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { RefreshCw, Truck } from 'lucide-vue-next'

import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import { dispatch, errorMessage } from '@/data/api'

const props = defineProps({ company: { type: String, required: true } })

const orders = ref([])
const loading = ref(false)
const error = ref(null)

const showPick = ref(false)
const picklist = ref(null)
const pickLoading = ref(false)
const pickError = ref(null)
const allocations = reactive({})
const scannedBatch = ref('')
const scanMessage = ref('')
function focusBatch() {
	const input = Array.from(document.querySelectorAll('input[data-batch]')).find((element) => element.dataset.batch === scannedBatch.value && !element.disabled)
	if (input) { input.focus(); input.select(); scanMessage.value = '' }
	else scanMessage.value = 'This batch is unavailable or blocked for this order.'
	scannedBatch.value = ''
}

const submitting = ref(false)
const submitError = ref(null)
const submitResult = ref(null)

const fmt = (value) => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })

async function load() {
	loading.value = true
	error.value = null
	try {
		orders.value = await dispatch.openOrders({ company: props.company })
	} catch (err) {
		error.value = err
	} finally {
		loading.value = false
	}
}

async function open(order) {
	showPick.value = true
	picklist.value = null
	pickError.value = null
	pickLoading.value = true
	submitError.value = null
	submitResult.value = null
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
	if (submitting.value || submitResult.value) return
	submitting.value = true
	submitError.value = null
	submitResult.value = null

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

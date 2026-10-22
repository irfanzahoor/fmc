<template>
	<section aria-labelledby="fm-disp-heading">
		<div class="mb-4 flex flex-wrap items-baseline gap-2">
			<h2 id="fm-disp-heading" class="text-lg font-semibold">Dispatch</h2>
			<p class="text-sm text-gray-600">Pick batches with a first-expiry-first-out suggestion.</p>
			<Button class="ml-auto fm-tap" :loading="loading" @click="load">Refresh</Button>
		</div>

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
					<p class="text-xs text-gray-600">{{ order.name }} · due {{ order.delivery_date || '—' }}</p>
					<p class="mt-2 text-sm">{{ fmt(order.per_delivered) }}% delivered</p>
					<Button class="fm-tap mt-3 w-full" variant="solid" @click="open(order)">Pick</Button>
				</li>
			</ul>
		</StateBlock>

		<Dialog v-model="showPick" :options="{ title: picklist?.sales_order || 'Pick', size: '3xl' }">
			<template #body-content>
				<StateBlock :loading="pickLoading" :error="pickError" loading-text="Loading picklist…">
					<div v-if="picklist" class="space-y-4">
						<p class="rounded bg-gray-100 p-2 text-sm">
							FEFO enforcement: <span class="font-medium">{{ picklist.fefo_mode }}</span>
							<template v-if="picklist.min_remaining_shelf_life_percent">
								· minimum shelf life {{ fmt(picklist.min_remaining_shelf_life_percent) }}%
							</template>
						</p>

						<form class="space-y-5" @submit.prevent="submit">
							<fieldset v-for="line in picklist.lines" :key="line.name" class="fm-card p-3">
								<legend class="px-1 text-sm font-medium">
									{{ line.item_name || line.item_code }} — {{ fmt(line.pending_qty) }} {{ line.uom }} outstanding
								</legend>

								<p v-if="line.shortfall" class="mb-2 rounded bg-red-50 p-2 text-sm text-red-800">
									Short by {{ fmt(line.shortfall) }} {{ line.stock_uom }} in {{ line.warehouse }}.
								</p>

								<p v-if="!line.candidates.length" class="text-sm text-red-700">
									No dispatchable batch in {{ line.warehouse }}.
								</p>

								<table v-else class="w-full text-left text-sm">
									<caption class="sr-only">Available batches in first-expiry-first-out order</caption>
									<thead>
										<tr class="border-b border-gray-200">
											<th scope="col" class="py-1 pr-3 font-medium">Batch</th>
											<th scope="col" class="py-1 pr-3 font-medium">Available</th>
											<th scope="col" class="py-1 pr-3 font-medium">Expiry</th>
											<th scope="col" class="py-1 pr-3 font-medium">Shelf life</th>
											<th scope="col" class="py-1 font-medium">Pick qty</th>
										</tr>
									</thead>
									<tbody>
										<tr
											v-for="(batch, index) in line.candidates"
											:key="batch.batch_no"
											class="border-b border-gray-100"
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
												<span v-else class="text-gray-500">—</span>
											</td>
											<td class="py-1">
												<input
													v-model="allocations[line.name][batch.batch_no]"
													type="number"
													step="any"
													min="0"
													:max="batch.available_qty"
													:disabled="Boolean(batch.blocked_reason)"
													class="fm-tap w-24 rounded border border-gray-300 px-2 py-1 disabled:bg-gray-100"
													:aria-label="`Pick quantity from batch ${batch.batch_no}`"
												/>
												<span v-if="batch.blocked_reason" class="block text-xs text-red-700">
													{{ batch.blocked_reason }}
												</span>
											</td>
										</tr>
									</tbody>
								</table>
							</fieldset>

							<p v-if="submitError" role="alert" class="rounded bg-red-50 p-2 text-sm text-red-800 whitespace-pre-line">
								{{ errorMessage(submitError) }}
							</p>

							<p v-if="submitResult" role="status" class="rounded bg-green-50 p-2 text-sm text-green-900">
								Dispatched as {{ submitResult.delivery_note }}.
							</p>

							<Button class="fm-tap" variant="solid" type="submit" :loading="submitting">
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
import { Truck } from 'lucide-vue-next'

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

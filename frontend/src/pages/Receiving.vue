<template>
	<section aria-labelledby="fm-recv-heading">
		<div class="mb-4 flex flex-wrap items-baseline gap-2">
			<h2 id="fm-recv-heading" class="text-lg font-semibold">Goods in</h2>
			<p class="text-sm text-gray-600">Receive against a purchase order and record the supplier lot.</p>
			<Button class="ml-auto fm-tap" :loading="loading" @click="load">Refresh</Button>
		</div>

		<StateBlock
			:loading="loading"
			:error="error"
			:empty="!orders.length"
			loading-text="Loading purchase orders…"
			empty-title="Nothing awaiting receipt"
			empty-hint="Submitted purchase orders with quantity outstanding will appear here."
			:icon="PackageCheck"
			:on-retry="load"
		>
			<ul class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
				<li v-for="order in orders" :key="order.name" class="fm-card p-4">
					<p class="font-medium">{{ order.supplier_name || order.supplier }}</p>
					<p class="text-xs text-gray-600">{{ order.name }} · {{ order.transaction_date }}</p>
					<p class="mt-2 text-sm">{{ fmt(order.per_received) }}% received</p>
					<Button class="fm-tap mt-3 w-full" variant="solid" @click="open(order)">Receive</Button>
				</li>
			</ul>
		</StateBlock>

		<Dialog v-model="showReceipt" :options="{ title: lines?.purchase_order || 'Receive', size: '3xl' }">
			<template #body-content>
				<StateBlock :loading="linesLoading" :error="linesError" loading-text="Loading lines…">
					<div v-if="lines" class="space-y-4">
						<p v-if="lines.requires_inspection" class="rounded bg-amber-50 p-2 text-sm text-amber-900">
							Inspected material will be routed to
							<span class="font-medium">{{ lines.quarantine_warehouse }}</span>
							and held until quality releases it.
						</p>

						<form class="space-y-4" @submit.prevent="submit">
							<div class="overflow-x-auto">
								<table class="w-full min-w-[44rem] text-left text-sm">
									<caption class="sr-only">Purchase order lines outstanding</caption>
									<thead class="border-b border-gray-200">
										<tr>
											<th scope="col" class="py-2 pr-3 font-medium">Item</th>
											<th scope="col" class="py-2 pr-3 font-medium">Outstanding</th>
											<th scope="col" class="py-2 pr-3 font-medium">Receive qty</th>
											<th scope="col" class="py-2 pr-3 font-medium">Supplier lot</th>
											<th scope="col" class="py-2 font-medium">Mfg date</th>
										</tr>
									</thead>
									<tbody>
										<tr v-for="line in lines.lines" :key="line.name" class="border-b border-gray-100">
											<td class="py-2 pr-3">
												<p>{{ line.item_name || line.item_code }}</p>
												<p v-if="line.needs_inspection" class="text-xs text-amber-800">
													needs inspection
												</p>
											</td>
											<td class="py-2 pr-3">{{ fmt(line.pending_qty) }} {{ line.uom }}</td>
											<td class="py-2 pr-3">
												<input
													v-model="entries[line.name].qty"
													type="number"
													step="any"
													min="0"
													:max="line.pending_qty"
													class="fm-tap w-24 rounded border border-gray-300 px-2 py-1"
													:aria-label="`Receive quantity for ${line.item_code}`"
												/>
											</td>
											<td class="py-2 pr-3">
												<input
													v-model="entries[line.name].supplier_lot_no"
													@keydown.enter.prevent
													placeholder="Scan supplier lot"
													type="text"
													class="fm-tap w-36 rounded border border-gray-300 px-2 py-1"
													:aria-label="`Supplier lot for ${line.item_code}`"
												/>
											</td>
											<td class="py-2">
												<input
													v-model="entries[line.name].supplier_mfg_date"
													type="date"
													class="fm-tap rounded border border-gray-300 px-2 py-1"
													:aria-label="`Manufacturing date for ${line.item_code}`"
												/>
											</td>
										</tr>
									</tbody>
								</table>
							</div>

							<p v-if="submitError" role="alert" class="rounded bg-red-50 p-2 text-sm text-red-800 whitespace-pre-line">
								{{ errorMessage(submitError) }}
							</p>

							<div v-if="submitResult" role="status" class="rounded bg-green-50 p-3 text-sm text-green-900">
								<p>Received as {{ submitResult.purchase_receipt }}.</p>
								<p v-if="submitResult.warehouses.length" class="mt-1">
									Stored in {{ submitResult.warehouses.join(', ') }}.
								</p>
								<ul v-if="submitResult.batches.length" class="mt-1 list-inside list-disc">
									<li v-for="batch in submitResult.batches" :key="batch.name">
										{{ batch.name }} — {{ batch.fm_quality_status || 'not managed' }}
									</li>
								</ul>
							</div>

							<Button class="fm-tap" variant="solid" type="submit" :loading="submitting" :disabled="submitting || Boolean(submitResult)">
								Post receipt
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
import { PackageCheck } from 'lucide-vue-next'

import StateBlock from '@/components/StateBlock.vue'
import { errorMessage, receiving } from '@/data/api'

const props = defineProps({ company: { type: String, required: true } })

const orders = ref([])
const loading = ref(false)
const error = ref(null)

const showReceipt = ref(false)
const lines = ref(null)
const linesLoading = ref(false)
const linesError = ref(null)
const entries = reactive({})

const submitting = ref(false)
const submitError = ref(null)
const submitResult = ref(null)

const fmt = (value) => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 3 })

async function load() {
	loading.value = true
	error.value = null
	try {
		orders.value = await receiving.openOrders({ company: props.company })
	} catch (err) {
		error.value = err
	} finally {
		loading.value = false
	}
}

async function open(order) {
	showReceipt.value = true
	lines.value = null
	linesError.value = null
	linesLoading.value = true
	submitError.value = null
	submitResult.value = null
	for (const key of Object.keys(entries)) delete entries[key]

	try {
		lines.value = await receiving.orderLines({ purchase_order: order.name })
		for (const line of lines.value.lines) {
			// Default to the full outstanding quantity: the common case is a
			// full receipt, and a partial one is just an edit.
			entries[line.name] = {
				qty: line.pending_qty,
				supplier_lot_no: '',
				supplier_mfg_date: '',
			}
		}
	} catch (err) {
		linesError.value = err
	} finally {
		linesLoading.value = false
	}
}

async function submit() {
	if (submitting.value || submitResult.value) return
	submitting.value = true
	submitError.value = null
	submitResult.value = null

	try {
		submitResult.value = await receiving.receive({
			purchase_order: lines.value.purchase_order,
			lines: Object.entries(entries).map(([name, values]) => ({ name, ...values })),
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

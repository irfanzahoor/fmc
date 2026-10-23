<template>
	<section aria-labelledby="fm-recv-heading">
		<PageHeader
			eyebrow="Receiving"
			title="Goods in"
			subtitle="Receive against a purchase order and record the supplier lot."
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
			loading-text="Loading purchase orders…"
			empty-title="Nothing awaiting receipt"
			empty-hint="Submitted purchase orders with quantity outstanding will appear here."
			:icon="PackageCheck"
			:on-retry="load"
		>
			<ul class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
				<li v-for="order in orders" :key="order.name" class="fm-card p-4">
					<p class="font-medium">{{ order.supplier_name || order.supplier }}</p>
					<p class="text-xs fm-muted">{{ order.name }} · {{ order.transaction_date }}</p>
					<p class="mt-2 text-sm">{{ fmt(order.per_received) }}% received</p>
					<button type="button" class="fm-btn-primary fm-tap mt-3 w-full px-4 text-sm" @click="open(order)">Receive</button>
				</li>
			</ul>
		</StateBlock>

		<Dialog v-model="showReceipt" :options="{ title: lines?.purchase_order || 'Receive', size: '3xl' }">
			<template #body-content>
				<StateBlock :loading="linesLoading" :error="linesError" loading-text="Loading lines…">
					<div v-if="lines" class="space-y-4">
						<p v-if="lines.requires_inspection" class="rounded-xl p-3 text-sm" :style="{ background: 'var(--fm-warn-bg)', color: 'var(--fm-warn)' }">
							Inspected material will be routed to
							<span class="font-medium">{{ lines.quarantine_warehouse }}</span>
							and held until quality releases it.
						</p>

						<form class="space-y-4" @submit.prevent="submit">
							<div class="overflow-x-auto">
								<table class="fm-table min-w-[44rem]">
									<caption class="sr-only">Purchase order lines outstanding</caption>
									<thead >
										<tr>
											<th scope="col" >Item</th>
											<th scope="col" >Outstanding</th>
											<th scope="col" >Receive qty</th>
											<th scope="col" >Supplier lot</th>
											<th scope="col" class="py-2 font-medium">Mfg date</th>
										</tr>
									</thead>
									<tbody>
										<tr v-for="line in lines.lines" :key="line.name" >
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
													class="fm-input fm-tap w-24"
													:aria-label="`Receive quantity for ${line.item_code}`"
												/>
											</td>
											<td class="py-2 pr-3">
												<input
													v-model="entries[line.name].supplier_lot_no"
													@keydown.enter.prevent
													placeholder="Scan supplier lot"
													type="text"
													class="fm-input fm-tap w-36"
													:aria-label="`Supplier lot for ${line.item_code}`"
												/>
											</td>
											<td class="py-2">
												<input
													v-model="entries[line.name].supplier_mfg_date"
													type="date"
													class="fm-input fm-tap"
													:aria-label="`Manufacturing date for ${line.item_code}`"
												/>
											</td>
										</tr>
									</tbody>
								</table>
							</div>

							<p v-if="submitError" role="alert" class="rounded-xl p-3 text-sm whitespace-pre-line" :style="{ background: 'var(--fm-bad-bg)', color: 'var(--fm-bad)' }">
								{{ errorMessage(submitError) }}
							</p>

							<div v-if="submitResult" role="status" class="rounded-xl p-3 text-sm" :style="{ background: 'var(--fm-good-bg)', color: 'var(--fm-good)' }">
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
import { PackageCheck, RefreshCw } from 'lucide-vue-next'

import PageHeader from '@/components/PageHeader.vue'
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

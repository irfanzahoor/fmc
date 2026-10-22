<template>
	<section aria-labelledby="fm-prod-heading">
		<div class="mb-4 flex flex-wrap items-baseline gap-2">
			<h2 id="fm-prod-heading" class="text-lg font-semibold">Production queue</h2>
			<p class="text-sm text-gray-600">Blending and packaging runs awaiting completion.</p>
			<Button class="ml-auto fm-tap" :loading="loading" @click="load">Refresh</Button>
		</div>

		<StateBlock
			:loading="loading"
			:error="error"
			:empty="!rows.length"
			loading-text="Loading production queue…"
			empty-title="No open production runs"
			empty-hint="Submitted Work Orders for this company will appear here."
			:icon="Factory"
			:on-retry="load"
		>
			<ul class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
				<li v-for="row in rows" :key="row.name" class="fm-card p-4">
					<div class="flex items-start justify-between gap-2">
						<div>
							<p class="font-medium">{{ row.item_name || row.production_item }}</p>
							<p class="text-xs text-gray-600">{{ row.name }}</p>
						</div>
						<Badge :theme="row.status === 'In Process' ? 'blue' : 'gray'">{{ row.status }}</Badge>
					</div>

					<dl class="mt-3 grid grid-cols-3 gap-2 text-sm">
						<div>
							<dt class="fm-label">Planned</dt>
							<dd>{{ fmt(row.qty) }} {{ row.stock_uom }}</dd>
						</div>
						<div>
							<dt class="fm-label">Done</dt>
							<dd>{{ fmt(row.produced_qty) }}</dd>
						</div>
						<div>
							<dt class="fm-label">Left</dt>
							<dd class="font-medium">{{ fmt(row.pending_qty) }}</dd>
						</div>
					</dl>

					<p v-if="row.fm_yield_flagged" class="mt-3 rounded bg-red-50 px-2 py-1 text-xs text-red-800">
						Yield variance {{ fmt(row.fm_yield_variance_percent) }}% — outside tolerance
					</p>

					<Button class="fm-tap mt-3 w-full" variant="solid" @click="open(row)">
						Open run
					</Button>
				</li>
			</ul>
		</StateBlock>

		<Dialog v-model="showRun" :options="{ title: detail?.work_order?.name || 'Run', size: '2xl' }">
			<template #body-content>
				<StateBlock :loading="detailLoading" :error="detailError" loading-text="Loading run…">
					<div v-if="detail" class="space-y-5">
						<div class="grid gap-3 sm:grid-cols-3">
							<div>
								<p class="fm-label">Item</p>
								<p class="text-sm">{{ detail.work_order.item_name || detail.work_order.production_item }}</p>
							</div>
							<div>
								<p class="fm-label">Planned</p>
								<p class="text-sm">{{ fmt(detail.work_order.qty) }} {{ detail.work_order.stock_uom }}</p>
							</div>
							<div>
								<p class="fm-label">Already produced</p>
								<p class="text-sm">{{ fmt(detail.work_order.produced_qty) }}</p>
							</div>
						</div>

						<div>
							<h3 class="mb-2 text-sm font-semibold">Ingredients and available lots</h3>
							<div class="overflow-x-auto">
								<table class="w-full min-w-[32rem] text-left text-sm">
									<caption class="sr-only">Required ingredients with released lots in FEFO order</caption>
									<thead>
										<tr class="border-b border-gray-200">
											<th scope="col" class="py-2 pr-3 font-medium">Ingredient</th>
											<th scope="col" class="py-2 pr-3 font-medium">Required</th>
											<th scope="col" class="py-2 pr-3 font-medium">Consumed</th>
											<th scope="col" class="py-2 font-medium">Released lots (earliest expiry first)</th>
										</tr>
									</thead>
									<tbody>
										<tr v-for="line in detail.ingredients" :key="line.item_code" class="border-b border-gray-100 align-top">
											<td class="py-2 pr-3">{{ line.item_name || line.item_code }}</td>
											<td class="py-2 pr-3">{{ fmt(line.required_qty) }} {{ line.stock_uom }}</td>
											<td class="py-2 pr-3">{{ fmt(line.consumed_qty) }}</td>
											<td class="py-2">
												<ul v-if="line.available_lots.length" class="space-y-1">
													<li v-for="lot in line.available_lots.slice(0, 4)" :key="lot.batch_no">
														<span class="font-mono text-xs">{{ lot.batch_no }}</span>
														<span class="text-gray-600"> · {{ fmt(lot.available_qty) }}</span>
														<span v-if="lot.expiry_date" class="text-gray-600"> · exp {{ lot.expiry_date }}</span>
													</li>
												</ul>
												<p v-else class="text-xs text-red-700">
													No released stock — needs a quality release first.
												</p>
											</td>
										</tr>
									</tbody>
								</table>
							</div>
						</div>

						<form class="grid gap-3 sm:grid-cols-3" @submit.prevent="finish">
							<FormControl
								v-model="form.qty"
								type="number"
								label="Good quantity"
								:description="`In ${detail.work_order.stock_uom}`"
								step="any"
								min="0"
								required
							/>
							<FormControl
								v-model="form.processLoss"
								type="number"
								label="Process loss"
								description="Non-recoverable"
								step="any"
								min="0"
							/>
							<FormControl
								v-model="form.finishedBatch"
								type="text"
								label="Output batch"
								description="Leave blank to let ERPNext name it"
							/>

							<p v-if="finishError" role="alert" class="sm:col-span-3 rounded bg-red-50 p-2 text-sm text-red-800 whitespace-pre-line">
								{{ errorMessage(finishError) }}
							</p>

							<p v-if="finishResult" role="status" class="sm:col-span-3 rounded bg-green-50 p-2 text-sm text-green-900">
								Posted {{ finishResult.stock_entry }} — yield
								{{ fmt(finishResult.yield_percent) }}%
								<template v-if="finishResult.yield_flagged"> (flagged, outside tolerance)</template>
							</p>

							<div class="sm:col-span-3">
								<Button class="fm-tap" variant="solid" :loading="finishing" type="submit">
									Finish run
								</Button>
							</div>
						</form>
					</div>
				</StateBlock>
			</template>
		</Dialog>
	</section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { Factory } from 'lucide-vue-next'

import StateBlock from '@/components/StateBlock.vue'
import { errorMessage, production } from '@/data/api'

const props = defineProps({ company: { type: String, required: true } })

const rows = ref([])
const loading = ref(false)
const error = ref(null)

const showRun = ref(false)
const detail = ref(null)
const detailLoading = ref(false)
const detailError = ref(null)

const finishing = ref(false)
const finishError = ref(null)
const finishResult = ref(null)
const form = reactive({ qty: '', processLoss: '', finishedBatch: '' })

const fmt = (value) => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 3 })

async function load() {
	loading.value = true
	error.value = null
	try {
		rows.value = await production.queue({ company: props.company })
	} catch (err) {
		error.value = err
	} finally {
		loading.value = false
	}
}

async function open(row) {
	showRun.value = true
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
	finishing.value = true
	finishError.value = null
	finishResult.value = null

	try {
		finishResult.value = await production.finishRun({
			work_order: detail.value.work_order.name,
			qty: form.qty,
			process_loss_qty: form.processLoss || 0,
			finished_batch: form.finishedBatch || null,
		})
		await load()
	} catch (err) {
		finishError.value = err
	} finally {
		finishing.value = false
	}
}

onMounted(load)
</script>

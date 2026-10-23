<template>
	<section>
		<PageHeader
			eyebrow="Receiving workspace"
			title="Goods in"
			subtitle="Every lot identified, inspected and accounted for."
		>
			<template #actions>
				<button type="button" class="fm-btn-ghost fm-tap flex items-center gap-2 px-3 text-sm" @click="load">
					<RefreshCw class="h-4 w-4" :class="loading ? 'animate-spin motion-reduce:animate-none' : ''" aria-hidden="true" />
					Refresh
				</button>
			</template>
		</PageHeader>

		<StateBlock
			:loading="loading && !orders.length"
			:error="error"
			:empty="!loading && !orders.length"
			loading-text="Loading purchase orders…"
			empty-title="Nothing awaiting receipt"
			empty-hint="Submitted purchase orders with quantity outstanding appear here."
			:icon="PackageCheck"
			:on-retry="load"
		>
			<ul class="mb-4 flex gap-3 overflow-x-auto pb-1">
				<li v-for="order in orders" :key="order.name" class="w-[16rem] shrink-0">
					<button
						type="button"
						class="fm-card w-full p-4 text-left"
						:style="selected === order.name ? { borderColor: 'var(--fm-primary)', boxShadow: '0 0 0 1px var(--fm-primary)' } : {}"
						:aria-current="selected === order.name ? 'true' : undefined"
						@click="open(order)"
					>
						<p class="font-bold">{{ order.supplier_name || order.supplier }}</p>
						<p class="fm-num mt-0.5 text-xs fm-muted">{{ order.name }} · {{ order.transaction_date }}</p>
						<p class="fm-num mt-2 text-xs fm-muted">{{ fmt(order.per_received) }}% received</p>
					</button>
				</li>
			</ul>

			<StateBlock v-if="selected" :loading="linesLoading" :error="linesError" loading-text="Loading lines…">
				<form v-if="lines" class="space-y-4" @submit.prevent="submit">
					<div class="fm-card p-5">
						<dl class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
							<div>
								<dt class="fm-label">Purchase order</dt>
								<dd class="fm-num mt-1 font-bold">{{ lines.purchase_order }}</dd>
								<dd class="text-xs fm-muted">{{ lines.lines.length }} outstanding line(s)</dd>
							</div>
							<div>
								<dt class="fm-label">Supplier</dt>
								<dd class="mt-1 font-bold">{{ lines.supplier_name || lines.supplier }}</dd>
								<dd class="text-xs fm-muted">Incoming material</dd>
							</div>
							<div>
								<dt class="fm-label">Destination</dt>
								<dd class="mt-1 font-bold">{{ lines.quarantine_warehouse || 'Order warehouse' }}</dd>
								<dd class="text-xs fm-muted">
									{{ lines.requires_inspection ? 'Policy routes inspected material here' : 'No inspection required' }}
								</dd>
							</div>
							<div>
								<dt class="fm-label">Lines to receive</dt>
								<dd class="fm-num mt-1 font-bold">{{ linesWithQty }}</dd>
								<dd class="text-xs fm-muted">Clear a quantity to skip a line</dd>
							</div>
						</dl>

						<p
							v-if="lines.requires_inspection"
							class="mt-4 flex items-start gap-2 rounded-xl p-3 text-sm"
							:style="{ background: 'var(--fm-warn-bg)', color: 'var(--fm-warn)' }"
						>
							<ShieldAlert class="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
							<span>
								Inspected material is routed to <strong>{{ lines.quarantine_warehouse }}</strong> and held until
								quality releases it. It cannot be consumed before then.
							</span>
						</p>
					</div>

					<div class="fm-card overflow-hidden">
						<div class="flex flex-wrap items-start justify-between gap-2 p-5 pb-3">
							<div>
								<h2 class="font-bold">Lines and supplier lots</h2>
								<p class="mt-0.5 text-sm fm-muted">Record what actually arrived, with its lot and manufacturing date.</p>
							</div>
							<span class="fm-chip fm-chip-soft">Enter does not post</span>
						</div>

						<div class="overflow-x-auto">
							<table class="fm-table min-w-[52rem]">
								<caption class="sr-only">Purchase order lines outstanding</caption>
								<thead>
									<tr>
										<th scope="col">Item</th>
										<th scope="col" class="text-right">Outstanding</th>
										<th scope="col" class="text-right">Receive</th>
										<th scope="col">Supplier lot</th>
										<th scope="col">Manufacturing date</th>
									</tr>
								</thead>
								<tbody>
									<tr v-for="line in lines.lines" :key="line.name">
										<td>
											<span class="block font-medium">{{ line.item_name || line.item_code }}</span>
											<span class="mt-0.5 flex flex-wrap items-center gap-1.5">
												<span class="fm-num text-xs fm-muted">{{ line.item_code }}</span>
												<span v-if="line.needs_inspection" class="fm-chip fm-chip-warn">
													<ShieldAlert class="h-3 w-3" aria-hidden="true" />
													Inspected
												</span>
											</span>
										</td>
										<td class="fm-num text-right">{{ fmt(line.pending_qty) }} {{ line.uom }}</td>
										<td class="text-right">
											<input
												v-model="entries[line.name].qty"
												type="number"
												step="any"
												min="0"
												:max="line.pending_qty"
												class="fm-input fm-tap w-24 text-right"
												:aria-label="`Receive quantity for ${line.item_code}`"
											/>
										</td>
										<td>
											<!-- A scanner's Enter must not post the receipt. -->
											<input
												v-model.trim="entries[line.name].supplier_lot_no"
												type="text"
												class="fm-input fm-tap fm-num w-40"
												placeholder="Scan or type"
												autocomplete="off"
												:aria-label="`Supplier lot for ${line.item_code}`"
												@keydown.enter.prevent
											/>
										</td>
										<td>
											<input
												v-model="entries[line.name].supplier_mfg_date"
												type="date"
												class="fm-input fm-tap"
												:aria-label="`Manufacturing date for ${line.item_code}`"
												@keydown.enter.prevent
											/>
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					</div>

					<p v-if="submitError" role="alert" class="whitespace-pre-line rounded-xl p-3 text-sm" :style="{ background: 'var(--fm-bad-bg)', color: 'var(--fm-bad)' }">
						{{ errorMessage(submitError) }}
					</p>

					<div v-if="submitResult" role="status" class="fm-card p-5">
						<p class="flex items-center gap-2 font-semibold" :style="{ color: 'var(--fm-good)' }">
							<CheckCircle class="h-4 w-4" aria-hidden="true" />
							Received as {{ submitResult.purchase_receipt }}
						</p>
						<p v-if="submitResult.warehouses.length" class="mt-1 text-sm fm-muted">
							Stored in {{ submitResult.warehouses.join(', ') }}.
						</p>
						<ul v-if="submitResult.batches.length" class="mt-3 grid gap-2 sm:grid-cols-2">
							<li v-for="batch in submitResult.batches" :key="batch.name" class="rounded-xl border p-3" :style="{ borderColor: 'var(--fm-border)' }">
								<p class="fm-num text-sm font-semibold">{{ batch.name }}</p>
								<p class="mt-0.5 text-xs fm-muted">{{ batch.item }}</p>
								<StatusChip class="mt-2" :status="batch.fm_quality_status" />
							</li>
						</ul>
					</div>

					<div class="fm-card flex flex-wrap items-center justify-between gap-3 p-4">
						<p class="text-xs fm-muted">Quarantine routing and batch creation are applied by the server.</p>
						<button type="submit" class="fm-btn-primary fm-tap flex items-center gap-2 px-4 text-sm" :disabled="submitting || Boolean(submitResult) || !linesWithQty">
							<Check class="h-4 w-4" aria-hidden="true" />
							{{ submitting ? 'Posting…' : submitResult ? 'Received' : 'Post receipt' }}
						</button>
					</div>
				</form>
			</StateBlock>

			<div v-else class="fm-card grid place-items-center p-10 text-center">
				<div>
					<PackageCheck class="mx-auto h-7 w-7 fm-muted" aria-hidden="true" />
					<p class="mt-2 text-sm font-semibold">Select a purchase order</p>
					<p class="mt-1 text-sm fm-muted">Its outstanding lines appear here.</p>
				</div>
			</div>
		</StateBlock>
	</section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Check, CheckCircle, PackageCheck, RefreshCw, ShieldAlert } from 'lucide-vue-next'

import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import StatusChip from '@/components/StatusChip.vue'
import { errorMessage, receiving } from '@/data/api'

const props = defineProps({ company: { type: String, required: true } })

const orders = ref([])
const loading = ref(false)
const error = ref(null)

const selected = ref(null)
const lines = ref(null)
const linesLoading = ref(false)
const linesError = ref(null)
const entries = reactive({})

const submitting = ref(false)
const submitError = ref(null)
const submitResult = ref(null)

const fmt = (value) => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 3 })

const linesWithQty = computed(
	() => Object.values(entries).filter((entry) => Number(entry.qty) > 0).length
)

async function load() {
	loading.value = true
	error.value = null
	try {
		orders.value = await receiving.openOrders({ company: props.company })
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
	lines.value = null
	linesError.value = null
	linesLoading.value = true
	submitError.value = null
	submitResult.value = null
	for (const key of Object.keys(entries)) delete entries[key]

	try {
		lines.value = await receiving.orderLines({ purchase_order: order.name })
		for (const line of lines.value.lines) {
			// Default to the full outstanding quantity: a full receipt is the
			// common case and a partial one is just an edit.
			entries[line.name] = { qty: line.pending_qty, supplier_lot_no: '', supplier_mfg_date: '' }
		}
	} catch (err) {
		linesError.value = err
	} finally {
		linesLoading.value = false
	}
}

async function submit() {
	// A confirmed receipt must not be posted twice by a second click.
	if (submitting.value || submitResult.value) return

	submitting.value = true
	submitError.value = null

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

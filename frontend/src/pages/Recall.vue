<template>
	<section>
		<PageHeader
			eyebrow="Traceability"
			title="Recall"
			subtitle="Trace a supplier or finished batch through production to customers."
		/>

		<form class="fm-card mb-4 flex flex-wrap items-end gap-3 p-4" @submit.prevent="load">
			<label class="min-w-[14rem] flex-1">
				<span class="fm-label">Batch</span>
				<input
					ref="batchInput"
					v-model.trim="batch"
					required
					class="fm-input fm-tap mt-1 fm-num"
					placeholder="Scan or enter a batch ID"
					autocomplete="off"
				/>
			</label>
			<button type="submit" class="fm-btn-primary fm-tap flex items-center gap-2 px-4 text-sm" :disabled="loading">
				<Search class="h-4 w-4" aria-hidden="true" />
				{{ loading ? 'Tracing…' : 'Trace affected deliveries' }}
			</button>
			<p class="w-full text-xs fm-muted">
				Read-only. Quantities use each item's stock UOM; a negative quantity is a customer return.
			</p>
		</form>

		<!-- Before a search the page explains what a trace returns, rather than
		     showing an empty canvas or inventing a result. -->
		<div v-if="!result && !loading && !error" class="fm-card p-6">
			<h2 class="font-bold">What a trace returns</h2>
			<p class="mt-0.5 text-sm fm-muted">Derived from submitted stock transactions, never from a stored graph.</p>

			<ol class="mt-4 grid gap-3 sm:grid-cols-3">
				<li v-for="(step, index) in steps" :key="step.title" class="rounded-xl p-4" :style="{ background: 'var(--fm-canvas)' }">
					<span class="fm-num flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold"
						:style="{ background: 'var(--fm-soft)', color: 'var(--fm-primary)' }">{{ index + 1 }}</span>
					<p class="mt-2 font-semibold">{{ step.title }}</p>
					<p class="mt-0.5 text-sm fm-muted">{{ step.hint }}</p>
				</li>
			</ol>

			<p class="mt-4 flex items-start gap-2 border-t pt-3 text-xs fm-muted" :style="{ borderColor: 'var(--fm-border)' }">
				<ShieldCheck class="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
				Cancelled transactions are excluded, so a cancelled delivery never appears as a phantom shipment.
			</p>
		</div>

		<StateBlock :loading="loading" :error="error" loading-text="Tracing batch…">
			<div v-if="result" class="space-y-4">
				<p
					v-if="result.truncated"
					role="alert"
					class="flex items-start gap-2 rounded-xl p-3 text-sm"
					:style="{ background: 'var(--fm-warn-bg)', color: 'var(--fm-warn)' }"
				>
					<AlertTriangle class="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
					<span>
						Trace limit reached, so this result is <strong>incomplete</strong>. Review the remaining
						batches before acting on a recall.
					</span>
				</p>

				<div class="fm-card p-5">
					<div class="flex flex-wrap items-baseline justify-between gap-2">
						<h2 class="font-bold">Affected batches</h2>
						<span class="fm-chip fm-chip-soft">{{ result.batches.length }}</span>
					</div>

					<p v-if="!result.batches.length" class="mt-3 text-sm fm-muted">
						No affected batch was found for that reference.
					</p>

					<ul v-else class="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
						<li
							v-for="row in result.batches"
							:key="row.name"
							class="rounded-xl border p-3"
							:style="{ borderColor: 'var(--fm-border)' }"
						>
							<p class="fm-num text-sm font-semibold">{{ row.name }}</p>
							<p class="mt-0.5 text-xs fm-muted">{{ row.item }}</p>
							<p v-if="row.fm_supplier_lot_no" class="mt-0.5 text-xs fm-muted">
								Supplier lot {{ row.fm_supplier_lot_no }}
							</p>
							<StatusChip class="mt-2" :status="row.fm_quality_status" />
						</li>
					</ul>
				</div>

				<div class="fm-card overflow-hidden">
					<div class="flex flex-wrap items-baseline justify-between gap-2 p-5 pb-3">
						<h2 class="font-bold">Customer deliveries and returns</h2>
						<span class="fm-chip fm-chip-soft">{{ result.deliveries.length }}</span>
					</div>

					<p v-if="!result.deliveries.length" class="px-5 pb-5 text-sm fm-muted">
						No submitted deliveries found for these batches.
					</p>

					<div v-else class="overflow-x-auto">
						<table class="fm-table min-w-[44rem]">
							<caption class="sr-only">Deliveries and returns for the affected batches</caption>
							<thead>
								<tr>
									<th scope="col">Delivery</th>
									<th scope="col">Customer</th>
									<th scope="col">Batch</th>
									<th scope="col">Date</th>
									<th scope="col">Stock qty</th>
									<th scope="col">Type</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="row in result.deliveries" :key="`${row.delivery_note}:${row.batch_no}`">
									<td>
										<a
											class="font-medium underline"
											:style="{ color: 'var(--fm-primary)' }"
											:href="`/app/delivery-note/${encodeURIComponent(row.delivery_note)}`"
										>{{ row.delivery_note }}</a>
									</td>
									<td>{{ row.customer }}</td>
									<td class="fm-num">{{ row.batch_no }}</td>
									<td class="fm-num">{{ row.posting_date }}</td>
									<td class="fm-num">{{ row.stock_qty }} {{ row.stock_uom }}</td>
									<td>
										<!-- A return is named, not just signed by a minus. -->
										<span class="fm-chip" :class="row.is_return ? 'fm-chip-warn' : 'fm-chip-soft'">
											<component :is="row.is_return ? Undo2 : Truck" class="h-3.5 w-3.5" aria-hidden="true" />
											{{ row.is_return ? 'Return' : 'Dispatch' }}
										</span>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>

				<div class="fm-card p-4">
					<p class="text-sm fm-muted">
						A hold or reject decision is audited and made in Quality — this page never changes stock.
					</p>
					<RouterLink :to="{ name: 'Quality' }" class="fm-btn-ghost fm-tap mt-3 inline-flex items-center gap-2 px-3 text-sm">
						<ShieldCheck class="h-4 w-4" aria-hidden="true" />
						Open the quality queue
					</RouterLink>
				</div>
			</div>
		</StateBlock>
	</section>
</template>

<script setup>
import { ref } from 'vue'
import { AlertTriangle, Search, ShieldCheck, Truck, Undo2 } from 'lucide-vue-next'

import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import { recall } from '@/data/api'
import StatusChip from '@/components/StatusChip.vue'

const props = defineProps({ company: { type: String, required: true } })

const steps = [
	{ title: 'Affected batches', hint: 'Every batch the scanned lot became, through blending and packing.' },
	{ title: 'Customer deliveries', hint: 'Where those batches shipped, and what came back as a return.' },
	{ title: 'An audited decision', hint: 'Hold or reject is recorded in Quality — this page changes nothing.' },
]

const batch = ref('')
const batchInput = ref(null)
const result = ref(null)
const loading = ref(false)
const error = ref(null)

async function load() {
	if (loading.value) return

	loading.value = true
	error.value = null
	result.value = null

	try {
		result.value = await recall.get({ batch: batch.value, company: props.company })
	} catch (err) {
		error.value = err
	} finally {
		loading.value = false
	}
}
</script>

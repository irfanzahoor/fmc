<template>
	<section aria-labelledby="recall-heading" class="space-y-4">
		<h2 id="recall-heading" class="text-lg font-semibold">Batch recall</h2>
		<p class="text-sm text-gray-600">Trace a supplier or finished batch through production to customers. Quantities use each item's stock UOM.</p>
		<form class="flex flex-wrap gap-2" @submit.prevent="load">
			<label class="flex items-center gap-2">Batch <input v-model.trim="batch" required class="fm-tap rounded border p-2" placeholder="Scan or enter batch ID" /></label>
			<Button type="submit" :loading="loading">Trace affected deliveries</Button>
		</form>
		<StateBlock :loading="loading" :error="error" loading-text="Tracing batch…">
			<div v-if="result" class="space-y-4">
				<p v-if="result.truncated" role="alert" class="rounded bg-amber-50 p-3">Trace limit reached. This result is incomplete; review the remaining batches before a recall.</p>
				<div class="fm-card p-4">
					<h3 class="font-semibold">Affected batches ({{ result.batches.length }})</h3>
					<ul class="mt-2 space-y-1"><li v-for="row in result.batches" :key="row.name">{{ row.name }} · {{ row.item }} · {{ row.fm_quality_status || 'Unmanaged' }}</li></ul>
				</div>
				<div class="fm-card overflow-x-auto p-4">
					<h3 class="mb-3 font-semibold">Customer deliveries and returns</h3>
					<p v-if="!result.deliveries.length">No submitted deliveries found.</p>
					<table v-else class="w-full min-w-[40rem] text-left text-sm">
						<thead><tr><th>Delivery</th><th>Customer</th><th>Batch</th><th>Date</th><th>Stock qty</th><th>Type</th></tr></thead>
						<tbody><tr v-for="row in result.deliveries" :key="`${row.delivery_note}:${row.batch_no}`" class="border-t">
							<td class="py-2"><a class="text-blue-700 underline" :href="`/app/delivery-note/${encodeURIComponent(row.delivery_note)}`">{{ row.delivery_note }}</a></td>
							<td>{{ row.customer }}</td><td>{{ row.batch_no }}</td><td>{{ row.posting_date }}</td><td>{{ row.stock_qty }} {{ row.stock_uom }}</td><td>{{ row.is_return ? 'Return' : 'Dispatch' }}</td>
						</tr></tbody>
					</table>
				</div>
			</div>
		</StateBlock>
	</section>
</template>
<script setup>
import { ref } from 'vue'
import { call } from 'frappe-ui'
import StateBlock from '@/components/StateBlock.vue'
const props = defineProps({ company: { type: String, required: true } })
const batch = ref('')
const result = ref(null)
const loading = ref(false)
const error = ref(null)
async function load() {
	if (loading.value) return
	loading.value = true
	error.value = null
	result.value = null
	try {
		result.value = await call('food_manufacturing.api.recall.get_recall', { batch: batch.value, company: props.company })
	} catch (err) { error.value = err } finally { loading.value = false }
}
</script>

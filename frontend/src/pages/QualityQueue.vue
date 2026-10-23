<template>
	<section aria-labelledby="fm-qc-heading">
		<PageHeader
			eyebrow="Quality workspace"
			title="Quality"
			subtitle="Batches awaiting a decision, longest-waiting first."
			:tabs="tabs"
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
			:empty="!rows.length"
			loading-text="Loading queue…"
			empty-title="Nothing awaiting quality"
			empty-hint="Quarantined and held batches with stock on hand will appear here."
			:icon="ClipboardCheck"
			:on-retry="load"
		>
			<div class="fm-card overflow-x-auto">
				<table class="fm-table min-w-[46rem]">
					<caption class="sr-only">Batches awaiting a quality decision</caption>
					<thead >
						<tr>
							<th scope="col" >Batch</th>
							<th scope="col" >Item</th>
							<th scope="col" >Status</th>
							<th scope="col" >Qty</th>
							<th scope="col" >Supplier lot</th>
							<th scope="col" >Shelf life left</th>
							<th scope="col" >Action</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="row in rows" :key="row.name" >
							<td class="px-3 py-2 font-mono text-xs">{{ row.name }}</td>
							<td >{{ row.item_name || row.item }}</td>
							<td >
								<Badge :theme="row.fm_quality_status === 'Hold' ? 'orange' : 'gray'">
									{{ row.fm_quality_status }}
								</Badge>
							</td>
							<td >{{ fmt(row.qty) }}</td>
							<td >{{ row.fm_supplier_lot_no || '—' }}</td>
							<td >
								<span v-if="row.remaining_shelf_life_percent !== null">
									{{ fmt(row.remaining_shelf_life_percent) }}%
								</span>
								<span v-else class="fm-muted">not tracked</span>
							</td>
							<td >
								<button type="button" class="fm-btn-ghost fm-tap px-3 text-sm" @click="open(row)">Decide</button>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</StateBlock>

		<div class="my-3 flex items-center gap-3">
			<Button :disabled="loading || pageStart === 0" @click="changePage(-100)">Previous</Button>
			<span class="text-sm">Page {{ Math.floor(pageStart / 100) + 1 }}</span>
			<Button :disabled="loading || rows.length < 100" @click="changePage(100)">Next</Button>
		</div>
		<Dialog v-model="showDecision" :options="{ title: 'Quality decision', size: 'xl' }">
			<template #body-content>
				<StateBlock :loading="contextLoading" :error="contextError" loading-text="Loading batch…">
					<div v-if="context" class="space-y-4">
						<dl class="grid gap-3 sm:grid-cols-3">
							<div>
								<dt class="fm-label">Batch</dt>
								<dd class="font-mono text-sm">{{ context.batch.name }}</dd>
							</div>
							<div>
								<dt class="fm-label">Item</dt>
								<dd class="text-sm">{{ context.batch.item_name || context.batch.item }}</dd>
							</div>
							<div>
								<dt class="fm-label">Current status</dt>
								<dd class="text-sm">{{ context.batch.quality_status || 'Not managed' }}</dd>
							</div>
							<div>
								<dt class="fm-label">Supplier</dt>
								<dd class="text-sm">{{ context.batch.supplier || '—' }}</dd>
							</div>
							<div>
								<dt class="fm-label">Supplier lot</dt>
								<dd class="text-sm">{{ context.batch.supplier_lot_no || '—' }}</dd>
							</div>
							<div>
								<dt class="fm-label">Expiry</dt>
								<dd class="text-sm">{{ context.batch.expiry_date || '—' }}</dd>
							</div>
						</dl>

						<div v-if="context.history.length">
							<h3 class="mb-1 text-sm font-semibold">Decision history</h3>
							<ul class="space-y-1 text-sm fm-muted">
								<li v-for="item in context.history" :key="item.name">
									<span class="font-medium">{{ item.decision }}</span>
									by {{ item.decided_by }} on {{ item.posting_datetime }}
									<span v-if="item.reason"> — {{ item.reason }}</span>
								</li>
							</ul>
						</div>

						<form class="space-y-3" @submit.prevent="submit">
							<fieldset>
								<legend class="fm-label mb-1">Decision</legend>
								<div class="flex flex-wrap gap-2">
									<label
										v-for="option in decisions"
										:key="option"
										class="fm-tap flex cursor-pointer items-center gap-2 rounded border px-3 py-2 text-sm"
										:class="form.decision === option ? 'border-gray-900 bg-gray-900 text-white' : 'border-gray-300'"
									>
										<input v-model="form.decision" type="radio" :value="option" class="sr-only" />
										{{ option }}
									</label>
								</div>
							</fieldset>

							<FormControl
								v-if="form.decision && form.decision !== 'Release'"
								v-model="form.reason"
								type="textarea"
								label="Reason"
								description="Mandatory when holding or rejecting"
								required
							/>

							<FormControl
								v-model="form.inspection"
								type="select"
								label="Quality Inspection"
								:options="inspectionOptions"
								description="Required to release when the company policy says so"
							/>

							<p v-if="submitError" role="alert" class="rounded-xl p-3 text-sm whitespace-pre-line" :style="{ background: 'var(--fm-bad-bg)', color: 'var(--fm-bad)' }">
								{{ errorMessage(submitError) }}
							</p>

							<p v-if="submitResult" role="status" class="rounded-xl p-3 text-sm" :style="{ background: 'var(--fm-good-bg)', color: 'var(--fm-good)' }">
								Recorded {{ submitResult.name }} — batch is now {{ submitResult.quality_status }}.
							</p>

							<Button class="fm-tap" variant="solid" type="submit" :loading="submitting" :disabled="!form.decision">
								Record decision
							</Button>
						</form>
					</div>
				</StateBlock>
			</template>
		</Dialog>
	</section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ClipboardCheck, RefreshCw, ShieldCheck } from 'lucide-vue-next'

import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import { errorMessage, quality } from '@/data/api'

const props = defineProps({ company: { type: String, required: true } })

const decisions = ['Release', 'Hold', 'Reject']

const tabs = [
	{ name: 'Quality', label: 'Workspace', icon: ShieldCheck },
	{ name: 'QualityInsights', label: 'Insights', icon: ClipboardCheck },
]

const rows = ref([])
const pageStart = ref(0)
async function changePage(delta) {
	pageStart.value = Math.max(0, pageStart.value + delta)
	await load()
}
const loading = ref(false)
const error = ref(null)

const showDecision = ref(false)
const context = ref(null)
const contextLoading = ref(false)
const contextError = ref(null)

const submitting = ref(false)
const submitError = ref(null)
const submitResult = ref(null)
const form = reactive({ decision: '', reason: '', inspection: '' })

const fmt = (value) => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })

const inspectionOptions = computed(() => [
	{ label: 'None', value: '' },
	...(context.value?.inspections || []).map((item) => ({
		label: `${item.name} (${item.status})`,
		value: item.name,
	})),
])

async function load() {
	loading.value = true
	error.value = null
	try {
		rows.value = await quality.queue({ company: props.company, start: pageStart.value, limit: 100 })
	} catch (err) {
		error.value = err
	} finally {
		loading.value = false
	}
}

async function open(row) {
	showDecision.value = true
	context.value = null
	contextError.value = null
	contextLoading.value = true
	submitError.value = null
	submitResult.value = null
	form.decision = ''
	form.reason = ''
	form.inspection = ''

	try {
		context.value = await quality.batchContext({ batch: row.name })
	} catch (err) {
		contextError.value = err
	} finally {
		contextLoading.value = false
	}
}

async function submit() {
	submitting.value = true
	submitError.value = null
	submitResult.value = null

	try {
		submitResult.value = await quality.recordDecision({
			batch: context.value.batch.name,
			company: props.company,
			decision: form.decision,
			reason: form.reason || null,
			quality_inspection: form.inspection || null,
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

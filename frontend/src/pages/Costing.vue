<template>
	<section>
		<PageHeader
			eyebrow="Costing workspace"
			title="Recipe cost and packaging"
			subtitle="What a batch would cost, and what packing it would need."
			:tabs="tabs"
		>
			<template #actions>
				<button type="button" class="fm-btn-ghost fm-tap flex items-center gap-2 px-3 text-sm" @click="load">
					<RefreshCw class="h-4 w-4" aria-hidden="true" />
					Refresh
				</button>
			</template>
		</PageHeader>

		<StateBlock
			:loading="loading && !boms.length"
			:error="error"
			:empty="!loading && !boms.length"
			loading-text="Loading approved recipes…"
			empty-title="No approved BOM to cost"
			empty-hint="Submit and activate a BOM for this company first."
			:icon="Calculator"
			:on-retry="load"
			:required-roles="SCREEN_ROLES.costing"
		>
			<div v-if="boms.length" class="space-y-4">
				<!-- Inputs first: everything below is a consequence of these. -->
				<div class="fm-card p-4">
					<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
						<label class="block">
							<span class="fm-label">Recipe (BOM)</span>
							<select v-model="bom" class="fm-input fm-tap mt-1 w-full" @change="onBom">
								<option v-for="row in boms" :key="row.name" :value="row.name">
									{{ row.item_name || row.item }} · {{ row.name }}
								</option>
							</select>
						</label>

						<label class="block">
							<span class="fm-label">Batch size</span>
							<span class="mt-1 flex items-center gap-2">
								<input
									v-model.number="batchQty"
									type="number" min="0" step="any"
									class="fm-input fm-tap w-full"
									@change="simulate"
								/>
								<span class="text-sm fm-muted">{{ selectedBom?.uom }}</span>
							</span>
						</label>

						<label class="block">
							<span class="fm-label">Yield</span>
							<span class="mt-1 flex items-center gap-2">
								<input
									v-model.number="yieldPercent"
									type="number" min="1" max="100" step="any"
									class="fm-input fm-tap w-full"
									@change="simulate"
								/>
								<span class="text-sm fm-muted">%</span>
							</span>
						</label>

						<label class="block">
							<span class="fm-label">Pack size</span>
							<select v-model="packItem" class="fm-input fm-tap mt-1 w-full" @change="simulate">
								<option value="">None</option>
								<option v-for="row in packs" :key="row.item_code" :value="row.item_code">
									{{ row.item_name || row.item_code }}
								</option>
							</select>
						</label>
					</div>
				</div>

				<StateBlock
					:loading="costingFlag"
					:error="costError"
					loading-text="Costing the batch…"
					:required-roles="SCREEN_ROLES.costing"
				>
					<div v-if="result" class="space-y-4">
						<!-- The distinction the brief turns on, stated before any figure. -->
						<p
							class="flex items-start gap-2 rounded-xl p-3 text-sm"
							:style="{ background: 'var(--fm-accent-soft)', color: 'var(--fm-accent-strong)' }"
						>
							<Info class="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
							<span>
								<strong>Estimated cost, not posted value.</strong>
								These figures price material that has not been consumed.
								What a finished batch actually cost comes from its submitted stock
								transactions.
							</span>
						</p>

						<div class="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
							<KpiCard label="Ingredients" :value="scenario.ingredient_cost" :unit="result.currency" :decimals="0" :icon="Wheat" />
							<KpiCard label="Packaging" :value="scenario.packaging_cost" :unit="result.currency" :decimals="0" :icon="Package" />
							<KpiCard label="Operating" :value="scenario.operating_cost" :unit="result.currency" :decimals="0" :icon="Settings" />
							<KpiCard
								label="Total per batch" :value="scenario.total_cost" :unit="result.currency"
								:decimals="0" :icon="Calculator" tone="neutral"
								:note="perUnitNote"
							/>
						</div>

						<div class="grid items-start gap-4 lg:grid-cols-2">
							<figure class="fm-card p-4">
								<figcaption class="mb-2">
									<h3 class="text-sm font-semibold">Ingredient breakdown</h3>
									<p class="text-xs fm-muted">
										Priced from the source this BOM declares. Conversions are shown, not assumed.
									</p>
								</figcaption>

								<!-- Formula access is permlevel-gated on the server; this just
								     reflects what came back. -->
								<p v-if="!result.shows_ingredient_detail" class="rounded-xl p-4 text-sm" :style="{ background: 'var(--fm-canvas)' }">
									<Lock class="mb-1 h-4 w-4" aria-hidden="true" />
									The totals above are yours to see; the per-ingredient formula is not.
									Ask an FM Recipe Manager.
								</p>

								<div v-else class="-mx-4 overflow-x-auto px-4">
									<table class="fm-table w-full min-w-[34rem] text-left text-sm">
										<thead>
											<tr>
												<th scope="col">Ingredient</th>
												<th scope="col" class="text-right">Quantity</th>
												<th scope="col" class="text-right">Rate</th>
												<th scope="col" class="text-right">Amount</th>
											</tr>
										</thead>
										<tbody>
											<tr v-for="line in scenario.ingredients" :key="line.item_code">
												<td>
													<span class="font-medium">{{ line.item_name || line.item_code }}</span>
													<span class="block text-[11px] fm-muted">{{ line.rate_source }}</span>
												</td>
												<td class="fm-num text-right">{{ fmt(line.qty) }} {{ line.uom }}</td>
												<td class="fm-num text-right">{{ fmt(line.rate) }}</td>
												<td class="fm-num text-right font-semibold">{{ fmt(line.amount) }}</td>
											</tr>
										</tbody>
									</table>
								</div>
							</figure>

							<figure class="fm-card p-4">
								<figcaption class="mb-2">
									<h3 class="text-sm font-semibold">Assumptions</h3>
									<p class="text-xs fm-muted">Everything the figures above rest on.</p>
								</figcaption>
								<ul class="space-y-1.5 text-sm">
									<li v-for="(note, index) in scenario.assumptions" :key="index" class="flex gap-2">
										<span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" :style="{ background: 'var(--fm-accent)' }" aria-hidden="true" />
										<span>{{ note }}</span>
									</li>
								</ul>

								<div v-if="scenario.packs.length" class="mt-4 border-t pt-3" :style="{ borderColor: 'var(--fm-border)' }">
									<p class="fm-label mb-2">Per pack</p>
									<ul class="space-y-1.5 text-sm">
										<li v-for="pack in scenario.packs" :key="pack.item_code" class="flex items-baseline justify-between gap-2">
											<span>{{ pack.item_name || pack.item_code }}</span>
											<span v-if="pack.cost_per_pack !== null" class="fm-num font-semibold">
												{{ result.currency }} {{ fmt(pack.cost_per_pack, 2) }}
											</span>
											<span v-else class="text-xs fm-muted">{{ pack.note }}</span>
										</li>
									</ul>
								</div>
							</figure>
						</div>
					</div>
				</StateBlock>

				<!-- Packaging plan -->
				<div class="fm-card p-4">
					<div class="flex flex-wrap items-start justify-between gap-3">
						<div>
							<h3 class="text-sm font-semibold">Packaging plan</h3>
							<p class="text-xs fm-muted">
								What a packing run needs, what is free, and the gap.
							</p>
						</div>
						<label class="flex items-center gap-2 text-sm">
							<span class="fm-muted">Packs</span>
							<input
								v-model.number="packQty"
								type="number" min="0" step="1"
								class="fm-input fm-tap w-28"
								:disabled="!packItem"
								@change="planPackaging"
							/>
						</label>
					</div>

					<p v-if="!packItem" class="mt-3 rounded-xl p-4 text-sm fm-muted" :style="{ background: 'var(--fm-canvas)' }">
						Choose a pack size above to plan its materials.
					</p>

					<StateBlock
						v-else
						:loading="planning"
						:error="planError"
						:empty="Boolean(plan) && !plan.lines.length"
						loading-text="Checking stock…"
						empty-title="Nothing to plan"
						empty-hint="This pack has no bulk item or packaging BOM yet."
						:required-roles="SCREEN_ROLES.costing"
					>
						<div v-if="plan && plan.lines.length" class="mt-3">
							<div class="-mx-4 overflow-x-auto px-4">
								<table class="fm-table w-full min-w-[46rem] text-left text-sm">
									<thead>
										<tr>
											<th scope="col">Material</th>
											<th scope="col" class="text-right">Required</th>
											<th scope="col" class="text-right">Free stock</th>
											<th scope="col" class="text-right">Requested</th>
											<th scope="col" class="text-right">Expected</th>
											<th scope="col" class="text-right">Short</th>
										</tr>
									</thead>
									<tbody>
										<tr v-for="line in plan.lines" :key="line.item_code">
											<td>
												<span class="font-medium">{{ line.item_name || line.item_code }}</span>
												<span v-if="line.conversion" class="block text-[11px] fm-muted">
													{{ line.conversion.from_qty }} {{ line.conversion.from_uom }}
													× {{ line.conversion.factor }} → {{ line.conversion.to_uom }}
												</span>
											</td>
											<td class="fm-num text-right">{{ fmt(line.required_qty) }} {{ line.uom }}</td>
											<td class="fm-num text-right">{{ fmt(line.available_qty) }}</td>
											<td class="fm-num text-right fm-muted">{{ fmt(line.requested_qty) }}</td>
											<td class="fm-num text-right fm-muted">{{ fmt(line.expected_qty) }}</td>
											<td class="text-right">
												<span
													v-if="line.shortage_qty > 0"
													class="fm-chip fm-chip-bad fm-num"
												>{{ fmt(line.shortage_qty) }}</span>
												<span v-else class="fm-chip fm-chip-good">covered</span>
											</td>
										</tr>
									</tbody>
								</table>
							</div>

							<ul v-if="plan.notes.length" class="mt-3 space-y-1 text-xs fm-muted">
								<li v-for="(note, index) in plan.notes" :key="index">{{ note }}</li>
							</ul>

							<p class="mt-3 text-xs fm-muted">
								Free stock is what is on hand less what is already promised.
								Requested and expected are open Material Requests and Purchase Orders,
								so planning the same run twice does not request it twice.
								Loss allowance {{ plan.loss_percent }}%.
							</p>
						</div>
					</StateBlock>
				</div>
			</div>
		</StateBlock>
	</section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { Calculator, Info, Lock, Package, RefreshCw, Settings, Wheat } from 'lucide-vue-next'

import KpiCard from '@/components/KpiCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import { SCREEN_ROLES } from '@/data/access'
import { costing } from '@/data/api'

const props = defineProps({ company: { type: String, required: true } })

const tabs = []

const boms = ref([])
const packs = ref([])
const bom = ref('')
const packItem = ref('')
const batchQty = ref(null)
const yieldPercent = ref(null)
const packQty = ref(1000)

const result = ref(null)
const plan = ref(null)
const loading = ref(false)
const costingFlag = ref(false)
const planning = ref(false)
const error = ref(null)
const costError = ref(null)
const planError = ref(null)

const selectedBom = computed(() => boms.value.find((row) => row.name === bom.value) || null)

/* Ask the server to cost every pack it knows about, so the picker has options
   before anything is chosen. */
const packCodes = computed(() =>
	packItem.value ? [packItem.value] : packs.value.map((row) => row.item_code)
)

/* A scenario exists only when something was overridden; otherwise the baseline
   is the answer. Reading one or the other keeps the template from branching. */
const scenario = computed(() => result.value?.scenario || result.value?.baseline || null)

const perUnitNote = computed(() => {
	if (!scenario.value?.cost_per_unit) return ''
	return `${fmt(scenario.value.cost_per_unit, 2)} per ${selectedBom.value?.uom || 'unit'}`
})

const fmt = (value, decimals = 0) =>
	value === null || value === undefined
		? '—'
		: Number(value).toLocaleString(undefined, {
				minimumFractionDigits: decimals,
				maximumFractionDigits: decimals,
			})

async function load() {
	loading.value = true
	error.value = null
	try {
		boms.value = await costing.boms({ company: props.company })
		if (boms.value.length) {
			bom.value = boms.value[0].name
			await onBom()
		}
	} catch (err) {
		error.value = err
	} finally {
		loading.value = false
	}
}

async function onBom() {
	batchQty.value = selectedBom.value?.quantity ?? null
	yieldPercent.value = null
	packs.value = await loadPacks()
	// Open on the first pack rather than "None": the planner is the point of
	// the screen, and an empty picker makes it look broken.
	packItem.value = packs.value[0]?.item_code || ''
	await simulate()
}

/** Finished goods filled from this BOM's product, for the pack picker. */
async function loadPacks() {
	const item = selectedBom.value?.item
	if (!item) return []
	try {
		return await costing.packsFor({ bulk_item: item })
	} catch {
		// Not fatal: costing still works, the picker is just empty.
		return []
	}
}

async function simulate() {
	if (!bom.value) return
	costingFlag.value = true
	costError.value = null
	try {
		result.value = await costing.simulate({
			bom: bom.value,
			batch_qty: batchQty.value || undefined,
			yield_percent: yieldPercent.value || undefined,
			packs: packCodes.value.length ? JSON.stringify(packCodes.value.map((code) => ({ item_code: code }))) : undefined,
		})
		// The pack list is whatever the server resolved; nothing is guessed
		// about which SKUs a blend fills.
		const resolved = result.value?.baseline?.packs || []
		if (resolved.length) packs.value = resolved
	} catch (err) {
		costError.value = err
	} finally {
		costingFlag.value = false
	}
	await planPackaging()
}

async function planPackaging() {
	if (!packItem.value || !packQty.value) {
		plan.value = null
		return
	}
	planning.value = true
	planError.value = null
	try {
		plan.value = await costing.planPackaging({
			company: props.company,
			packs: JSON.stringify([{ item_code: packItem.value, qty: packQty.value }]),
		})
	} catch (err) {
		planError.value = err
	} finally {
		planning.value = false
	}
}

watch(() => props.company, load)
onMounted(load)
</script>

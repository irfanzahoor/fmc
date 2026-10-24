<template>
	<section>
		<PageHeader
			eyebrow="My workspace"
			:title="title"
			subtitle="Figures from this company's own records. Every one opens what it counts."
		>
			<template #actions>
				<button type="button" class="fm-btn-ghost fm-tap flex items-center gap-2 px-3 text-sm" @click="load">
					<RefreshCw class="h-4 w-4" aria-hidden="true" />
					Refresh
				</button>
			</template>
		</PageHeader>

		<!-- One filter row above everything it scopes, not per panel. -->
		<div class="mb-4 flex flex-wrap items-center gap-2">
			<div v-if="views.length > 1" class="flex flex-wrap gap-1.5" role="group" aria-label="Dashboard">
				<button
					v-for="option in views"
					:key="option"
					type="button"
					class="fm-tap rounded-xl px-3 text-sm font-medium capitalize transition-colors motion-reduce:transition-none"
					:class="option === view ? 'fm-btn-primary' : 'fm-btn-ghost'"
					:aria-pressed="option === view"
					@click="select(option)"
				>
					{{ option }}
				</button>
			</div>

			<label class="ml-auto flex items-center gap-2 text-sm">
				<span class="fm-muted">Period</span>
				<select v-model.number="days" class="fm-input fm-tap px-3 text-sm" @change="load">
					<option :value="7">Last 7 days</option>
					<option :value="30">Last 30 days</option>
					<option :value="90">Last 90 days</option>
				</select>
			</label>
		</div>

		<StateBlock
			:loading="loading && !data"
			:error="error"
			:empty="Boolean(data) && !data.panels.length"
			loading-text="Building your workspace…"
			empty-title="Nothing to show yet"
			empty-hint="This company has no activity in the period you picked."
			:icon="LayoutDashboard"
			:on-retry="load"
			:required-roles="SCREEN_ROLES.overview"
		>
			<div v-if="data" class="space-y-4">
				<section v-for="panel in data.panels" :key="panel.title">
					<div class="mb-2 flex flex-wrap items-baseline justify-between gap-2">
						<h2 class="text-base font-bold">{{ panel.title }}</h2>
						<p v-if="panel.note" class="text-xs fm-muted">{{ panel.note }}</p>
					</div>

					<div class="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
						<MetricCard
							v-for="metric in panel.metrics"
							:key="metric.label"
							:metric="metric"
							:currency="data.currency"
						/>
					</div>

					<!-- A count tells you there is a problem; the rows tell you
					     which one, and what to do about it. Only a panel that
					     says its rows are shortages gets the shortage template. -->
					<div v-if="panel.kind === 'material_short' && panel.rows.length" class="fm-card mt-3 p-4">
						<ExceptionList
							:rows="panel.rows"
							:more="Math.max(0, panel.total - panel.rows.length)"
						/>
					</div>
				</section>

				<p class="text-xs fm-muted">
					Counts cover {{ data.company }} only, from {{ data.since }}.
					A figure with no number has not been measured — it is not a zero.
				</p>
			</div>
		</StateBlock>
	</section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { LayoutDashboard, RefreshCw } from 'lucide-vue-next'

import ExceptionList from '@/components/ExceptionList.vue'
import MetricCard from '@/components/MetricCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import { SCREEN_ROLES } from '@/data/access'
import { roleDashboard } from '@/data/api'

const props = defineProps({ company: { type: String, required: true } })

const TITLES = {
	owner: 'Plant performance',
	production: 'Production workspace',
	quality: 'Quality workspace',
	stores: 'Stores workspace',
}

const data = ref(null)
const views = ref([])
const view = ref('production')
const days = ref(30)
const loading = ref(false)
const error = ref(null)

const title = computed(() => TITLES[view.value] || 'My workspace')

function select(option) {
	view.value = option
	load()
}

async function load() {
	loading.value = true
	error.value = null
	try {
		// The server decides which dashboards this account's roles fit; the
		// endpoints re-check permission regardless.
		if (!views.value.length) {
			views.value = await roleDashboard.views()
			if (views.value.length) view.value = views.value[0]
		}
		data.value = await roleDashboard.get({
			company: props.company,
			view: view.value,
			days: days.value,
		})
	} catch (err) {
		error.value = err
	} finally {
		loading.value = false
	}
}

watch(() => props.company, load)
onMounted(load)
</script>

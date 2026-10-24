import { createRouter, createWebHistory } from 'vue-router'

export const routes = [
	{ path: '/', redirect: { name: 'Dashboard' } },
	{
		path: '/dashboard',
		name: 'Dashboard',
		component: () => import('@/pages/Dashboard.vue'),
		meta: { title: 'Overview' },
	},
	{
		path: '/production',
		name: 'Production',
		component: () => import('@/pages/ProductionConsole.vue'),
		meta: { title: 'Production' },
	},
	{
		path: '/quality',
		name: 'Quality',
		component: () => import('@/pages/QualityQueue.vue'),
		meta: { title: 'Quality' },
	},
	{
		path: '/receiving',
		name: 'Receiving',
		component: () => import('@/pages/Receiving.vue'),
		meta: { title: 'Receiving' },
	},
	{
		path: '/dispatch',
		name: 'Dispatch',
		component: () => import('@/pages/Dispatch.vue'),
		meta: { title: 'Dispatch' },
	},
	{
		path: '/recall',
		name: 'Recall',
		component: () => import('@/pages/Recall.vue'),
		meta: { title: 'Recall' },
	},
	{
		path: '/insights/production',
		name: 'ProductionInsights',
		component: () => import('@/pages/ProductionInsights.vue'),
		meta: { title: 'Production insights' },
	},
	{
		path: '/insights/quality',
		name: 'QualityInsights',
		component: () => import('@/pages/QualityInsights.vue'),
		meta: { title: 'Quality overview' },
	},
	{
		path: '/costing',
		name: 'Costing',
		component: () => import('@/pages/Costing.vue'),
		meta: { title: 'Recipe cost and packaging' },
	},
	{
		path: '/workspace',
		name: 'Workspace',
		component: () => import('@/pages/RoleDashboard.vue'),
		meta: { title: 'My workspace' },
	},
	// Without this, a mistyped or stale link under /fm renders the shell with
	// an empty pane and no explanation.
	{
		path: '/:pathMatch(.*)*',
		name: 'NotFound',
		component: () => import('@/pages/NotFound.vue'),
		meta: { title: 'Page not found' },
	},
]

const router = createRouter({
	history: createWebHistory('/fm'),
	routes,
})

router.afterEach((to) => {
	document.title = to.meta?.title ? `${to.meta.title} · Food Manufacturing` : 'Food Manufacturing'
})

export default router

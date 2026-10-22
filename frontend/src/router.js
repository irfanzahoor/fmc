import { createRouter, createWebHistory } from 'vue-router'

const routes = [
	{ path: '/', redirect: { name: 'Production' } },
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
]

const router = createRouter({
	history: createWebHistory('/fm'),
	routes,
})

router.afterEach((to) => {
	document.title = to.meta?.title ? `${to.meta.title} · Food Manufacturing` : 'Food Manufacturing'
})

export default router

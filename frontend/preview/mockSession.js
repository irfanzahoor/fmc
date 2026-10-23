import { reactive } from 'vue'

/** Mock of @/data/session for the harness: no network, one company. */
export const session = reactive({
	user: 'demo@fmc.local',
	roles: ['System Manager'],
	companies: ['FM Demo Foods'],
	company: 'FM Demo Foods',
	loading: false,
	error: null,
	hasRole: () => true,
	setCompany(value) {
		this.company = value
	},
	async load() {},
})

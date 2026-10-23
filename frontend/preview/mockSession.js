import { reactive } from 'vue'

/**
 * Mock of @/data/session for the harness.
 *
 * Deliberately mirrors the real site: several companies, only one of which has
 * an FM Manufacturing Policy. That is the case that made the live app look
 * empty, so the harness has to reproduce it.
 */
const COMPANIES = [
	'Steps ERP',
	'Steps ERP (Demo)',
	'Steps Real Estate (Qatar)',
	'Steps Real Estate Group',
]
const CONFIGURED = ['Steps ERP (Demo)']

export const session = reactive({
	user: 'demo@fmc.local',
	roles: ['System Manager'],
	companies: COMPANIES,
	configuredCompanies: CONFIGURED,
	company: CONFIGURED[0],
	loading: false,
	error: null,
	hasRole: () => true,
	isConfigured(company) {
		return this.configuredCompanies.includes(company || this.company)
	},
	setCompany(value) {
		this.company = value
	},
	async load() {},
})

import { reactive } from 'vue'
import { call } from 'frappe-ui'

/**
 * Who is logged in, and which company they are working in.
 *
 * The company is a browser preference and is never trusted: every endpoint
 * re-checks permission server-side, so choosing a company you cannot see
 * returns nothing rather than someone else's data.
 */
const STORAGE_KEY = 'fm:company'

function readStored() {
	try {
		return localStorage.getItem(STORAGE_KEY)
	} catch {
		// Private window or blocked storage: start with no remembered choice.
		return null
	}
}

/*
 * Boot data is written onto `window` key by key by the page template, so these
 * live at the top level - not under `window.frappe.boot`, which this SPA does
 * not have.
 */
const boot = window.fm_boot || {}

export const session = reactive({
	user: boot.user || null,
	roles: boot.roles || [],
	companies: [],
	// Companies that actually have an FM Manufacturing Policy. Only these have
	// anything for this app to show.
	configuredCompanies: [],
	company: readStored(),
	loading: false,
	error: null,

	hasRole(role) {
		return this.roles.includes(role) || this.roles.includes('System Manager')
	},

	isConfigured(company) {
		return this.configuredCompanies.includes(company || this.company)
	},

	setCompany(company) {
		this.company = company
		try {
			localStorage.setItem(STORAGE_KEY, company)
		} catch {
			// The choice simply will not persist.
		}
	},

	/**
	 * Which company to open on.
	 *
	 * Landing on a company with no FM policy shows an empty dashboard and reads
	 * as a broken app, so a configured company wins over a merely alphabetical
	 * first one. Order: a remembered choice, then the user's own ERPNext
	 * default, then the first configured company, then the first company.
	 */
	pickCompany(stored) {
		const configured = this.configuredCompanies

		// A remembered choice wins - but not a remembered choice that has
		// nothing to show while a configured company exists. Letting it win is
		// how a browser gets permanently stuck on an empty company: the value
		// was stored on a first visit and then re-chosen on every visit after.
		if (stored && this.companies.includes(stored)) {
			if (!configured.length || configured.includes(stored)) return stored
		}

		const userDefault = window.sysdefaults?.company
		if (userDefault && configured.includes(userDefault)) return userDefault

		if (configured.length) return configured[0]
		if (userDefault && this.companies.includes(userDefault)) return userDefault

		return this.companies[0] || null
	},

	async load() {
		this.loading = true
		this.error = null

		try {
			const companies = await call('frappe.client.get_list', {
				doctype: 'Company',
				fields: ['name'],
				limit_page_length: 0,
				order_by: 'name asc',
			})
			this.companies = companies.map((row) => row.name)

			try {
				const policies = await call('frappe.client.get_list', {
					doctype: 'FM Manufacturing Policy',
					filters: { enabled: 1 },
					fields: ['name'],
					limit_page_length: 0,
					order_by: 'name asc',
				})
				// The policy is named after its company.
				this.configuredCompanies = policies
					.map((row) => row.name)
					.filter((name) => this.companies.includes(name))
			} catch {
				// No read access to the policy is not fatal; fall back to all
				// companies rather than refusing to render.
				this.configuredCompanies = []
			}

			const chosen = this.pickCompany(this.company)
			if (chosen && chosen !== this.company) {
				this.setCompany(chosen)
			} else if (chosen) {
				this.company = chosen
			}
		} catch (error) {
			this.error = error
		} finally {
			this.loading = false
		}
	},
})

import { reactive } from 'vue'

import { bootstrap } from '@/data/api'

/**
 * Who is logged in, and which company they are working in.
 *
 * The company is a browser preference and is never trusted: every endpoint
 * re-checks permission server-side, so choosing a company you cannot see
 * returns nothing rather than someone else's data.
 *
 * The list comes from one app endpoint rather than a direct Company query:
 * Company is not readable by the FM roles, so an operator holding only those
 * roles could not get past the first request.
 */
const STORAGE_KEY = 'fm:company'

/*
 * Boot data is written onto `window` key by key by the page template, so these
 * live at the top level - not under `window.frappe.boot`, which this SPA does
 * not have.
 */
const boot = window.fm_boot || {}

function readStored() {
	try {
		return localStorage.getItem(STORAGE_KEY)
	} catch {
		// Private window or blocked storage: start with no remembered choice.
		return null
	}
}

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
	 * A remembered choice wins - but not one that has nothing to show while a
	 * configured company exists. Letting it win is how a browser gets stuck on
	 * an empty company: the value is stored on a first visit and re-chosen on
	 * every visit after.
	 */
	pickCompany(stored, serverDefault) {
		const configured = this.configuredCompanies

		if (stored && this.companies.includes(stored)) {
			if (!configured.length || configured.includes(stored)) return stored
		}

		if (serverDefault && this.companies.includes(serverDefault)) return serverDefault
		if (configured.length) return configured[0]

		return this.companies[0] || null
	},

	async load() {
		this.loading = true
		this.error = null

		try {
			const data = await bootstrap.get()

			this.companies = data.companies || []
			this.configuredCompanies = data.configured || []
			if (data.user) this.user = data.user

			const chosen = this.pickCompany(this.company, data.default)
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

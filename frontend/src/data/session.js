import { reactive } from 'vue'
import { call } from 'frappe-ui'

/**
 * Who is logged in, and which company they are working in.
 *
 * The company is a user preference held in the browser, but it is never
 * trusted: every endpoint re-checks permission server-side, so picking a
 * company you cannot see returns nothing rather than someone else's data.
 */
const STORAGE_KEY = 'fm:company'

export const session = reactive({
	user: window.frappe?.boot?.user?.name || null,
	roles: window.frappe?.boot?.user?.roles || [],
	companies: [],
	company: localStorage.getItem(STORAGE_KEY) || null,
	loading: false,
	error: null,

	hasRole(role) {
		return this.roles.includes(role) || this.roles.includes('System Manager')
	},

	setCompany(company) {
		this.company = company
		try {
			localStorage.setItem(STORAGE_KEY, company)
		} catch (error) {
			// Private browsing or blocked storage: the choice just will not persist.
		}
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
			if (!this.company || !this.companies.includes(this.company)) {
				this.company = this.companies[0] || null
				if (this.company) this.setCompany(this.company)
			}
		} catch (error) {
			this.error = error
		} finally {
			this.loading = false
		}
	},
})

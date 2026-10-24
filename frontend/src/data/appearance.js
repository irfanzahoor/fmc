import { reactive, watch } from 'vue'

/**
 * Theme and typography preference.
 *
 * Stored per browser, never on the server: it is a display preference, not
 * business data. Every read and write is guarded, because storage throws in a
 * private window and returns nothing with site data cleared - the app must
 * still render with the defaults in that case.
 */
export const THEMES = [
	{ value: 'midnight', label: 'Midnight Blue', swatch: '#111d33', accent: '#4263eb' },
	{ value: 'forest', label: 'Batchwell', swatch: '#09301b', accent: '#0c4224' },
	{ value: 'amethyst', label: 'Amethyst', swatch: '#251d39', accent: '#7552b5' },
	{ value: 'graphite', label: 'Graphite', swatch: '#202831', accent: '#445366' },
	{ value: 'copper', label: 'Copper', swatch: '#342a23', accent: '#9c5b35' },
]

export const FONTS = [
	{ value: 'studio', label: 'Studio', hint: 'Plus Jakarta Sans headings · Inter body' },
	{ value: 'humanist', label: 'Humanist', hint: 'Inter headings · Plus Jakarta Sans body' },
]

const THEME_KEY = 'fm:theme'
const FONT_KEY = 'fm:font'

function read(key, fallback, allowed) {
	try {
		const value = localStorage.getItem(key)
		return allowed.includes(value) ? value : fallback
	} catch {
		return fallback
	}
}

function write(key, value) {
	try {
		localStorage.setItem(key, value)
	} catch {
		// Private window or blocked storage: the choice just will not persist.
	}
}

export const appearance = reactive({
	// Forest is Batchwell's own palette; the rest stay selectable.
	theme: read(THEME_KEY, 'forest', THEMES.map((t) => t.value)),
	font: read(FONT_KEY, 'studio', FONTS.map((f) => f.value)),

	setTheme(value) {
		if (!THEMES.some((t) => t.value === value)) return
		this.theme = value
	},

	setFont(value) {
		if (!FONTS.some((f) => f.value === value)) return
		this.font = value
	},
})

watch(() => appearance.theme, (value) => write(THEME_KEY, value))
watch(() => appearance.font, (value) => write(FONT_KEY, value))

import '../src/index.css'

import { createApp } from 'vue'
import { Badge, Button, Dialog, FeatherIcon, FormControl, FrappeUI, Spinner } from 'frappe-ui'

import { createRouter, createWebHashHistory } from 'vue-router'

import App from '../src/App.vue'
import { routes } from '../src/router'

// Hash history so every route is reachable from a static file server; the app
// itself uses history mode under /fm.
const router = createRouter({ history: createWebHashHistory(), routes })

/*
 * Mounts the REAL shell, router and pages. Only @/data/api and @/data/session
 * are aliased to mocks by vite.preview.config.js, so what renders here is what
 * renders against a live site.
 */
const app = createApp(App)
app.use(FrappeUI)
app.use(router)

for (const [name, component] of Object.entries({ Badge, Button, Dialog, FeatherIcon, FormControl, Spinner })) {
	app.component(name, component)
}

app.mount('#app')

/*
 * `?hover=<selector>` drives one pointer interaction after mount.
 *
 * Headless Chrome takes a screenshot but never moves a mouse, so a tooltip or
 * hover state cannot otherwise be looked at - and a chart's hover layer is a
 * required part of it, not a nicety. Harness-only: nothing here ships.
 */
const hover = new URLSearchParams(location.search).get('hover')
if (hover) {
	setTimeout(() => {
		const target = document.querySelector(hover)
		if (!target) return console.warn('[harness] no element for', hover)

		const box = target.getBoundingClientRect()
		const x = box.left + box.width * 0.62
		const y = box.top + box.height / 2
		for (const type of ['pointerenter', 'pointermove']) {
			target.dispatchEvent(
				new PointerEvent(type, { clientX: x, clientY: y, bubbles: true })
			)
		}
	}, 900)
}

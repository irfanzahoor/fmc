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

import './index.css'

import { createApp } from 'vue'
import { Badge, Button, Dialog, FeatherIcon, FormControl, FrappeUI, Spinner, frappeRequest, setConfig } from 'frappe-ui'

import App from './App.vue'
import router from './router'

const app = createApp(App)

setConfig('resourceFetcher', frappeRequest)
app.use(FrappeUI)
app.use(router)

for (const [name, component] of Object.entries({
	Badge,
	Button,
	Dialog,
	FeatherIcon,
	FormControl,
	Spinner,
})) {
	app.component(name, component)
}

app.mount('#app')

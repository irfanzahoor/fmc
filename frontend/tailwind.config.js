// frappe-ui 0.1.278 exposes the preset at `frappe-ui/tailwind`; the older
// `frappe-ui/src/tailwind/preset` subpath is no longer in its exports map.
import frappeUIPreset from 'frappe-ui/tailwind'

export default {
  presets: [frappeUIPreset],
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
    './node_modules/frappe-ui/src/**/*.{vue,js,ts}',
    './node_modules/frappe-ui/frappe/**/*.{vue,js,ts}',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}

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
    extend: {
      /*
       * frappe-ui's preset replaces Tailwind's font-size scale and stops at
       * `text-2xl` (20px) - `text-4xl` and `text-5xl` generate no CSS at all,
       * so a hero number written with them silently renders at base size.
       * This adds the one step the dashboard needs, as its own named token.
       */
      fontSize: {
        'fm-hero': ['2.25rem', { lineHeight: '1.1', letterSpacing: '-0.02em' }],
      },
    },
  },
  plugins: [],
}

import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'

/**
 * Design harness only. Builds `preview/` as standalone static pages so the real
 * shell, router and pages can be opened and screenshotted without a Frappe
 * session. `@/data/api` and `@/data/session` are aliased to mocks; everything
 * else is the application's own code. Never shipped - the app build uses
 * vite.config.js.
 */
export default defineConfig({
  root: path.resolve(__dirname, 'preview'),
  base: './',
  // frappe-ui components import `~icons/lucide/*`, which only its own plugin
  // resolves; the proxy and Jinja boot data are off because the harness has no
  // Frappe server behind it.
  plugins: [frappeui({ frappeProxy: false, lucideIcons: true, jinjaBootData: false, buildConfig: false }), vue()],
  resolve: {
    alias: [
      { find: '@/data/api', replacement: path.resolve(__dirname, 'preview/mockApi.js') },
      { find: '@/data/session', replacement: path.resolve(__dirname, 'preview/mockSession.js') },
      { find: '@', replacement: path.resolve(__dirname, 'src') },
    ],
  },
  css: { postcss: path.resolve(__dirname) },
  build: {
    outDir: process.env.FM_PREVIEW_OUT || path.resolve(__dirname, '../../../../tmp/fm-preview'),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        index: path.resolve(__dirname, 'preview/index.html'),
        pages: path.resolve(__dirname, 'preview/pages.html'),
      },
    },
  },
})

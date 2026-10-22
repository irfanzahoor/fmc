import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

/**
 * Design harness only. Builds `preview/` as a standalone static page with
 * fixture data, so the real chart components can be opened and screenshotted
 * without a Frappe session. Never shipped - the app build uses vite.config.js.
 */
export default defineConfig({
  root: path.resolve(__dirname, 'preview'),
  base: './',
  plugins: [vue()],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  css: {
    postcss: path.resolve(__dirname),
  },
  build: {
    outDir: process.env.FM_PREVIEW_OUT || path.resolve(__dirname, '../../../../tmp/fm-preview'),
    emptyOutDir: true,
  },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Django serves the built assets under /static/, so the production bundle has to
// reference them there. The dev server instead serves from the root: React Router
// owns paths like /login and /r/<slug>-<token>, and they have to survive a hard
// refresh, which a /static/ base would turn into a 404.
export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === 'build' ? '/static/' : '/',
  build: {
    outDir: '../backend/frontend_build',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
}))

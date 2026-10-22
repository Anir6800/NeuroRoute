import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Local only: dev server on loopback; /api is proxied to the local backend (no CORS needed).
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: { environment: 'jsdom' },
})

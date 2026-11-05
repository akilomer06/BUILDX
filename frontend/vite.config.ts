import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  define: { __VERCEL_HOSTED__: JSON.stringify(process.env.VERCEL === '1') },
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: process.env.VITE_API_PROXY || 'http://127.0.0.1:8000', changeOrigin: true },
      '/health': { target: process.env.VITE_API_PROXY || 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  test: { environment: 'jsdom', setupFiles: './src/test-setup.ts', css: false },
})

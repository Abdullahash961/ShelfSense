import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api/ws': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/captures': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/references': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})

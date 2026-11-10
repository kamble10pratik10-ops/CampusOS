import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/auth': 'http://127.0.0.1:8000',
      '/dashboard': 'http://127.0.0.1:8000',
      '/conflicts': 'http://127.0.0.1:8000',
      '/workload': 'http://127.0.0.1:8000',
      '/planner': 'http://127.0.0.1:8000',
      '/simulation': 'http://127.0.0.1:8000',
      '/whatif': 'http://127.0.0.1:8000',
      '/decisions': 'http://127.0.0.1:8000',
      '/faculty': 'http://127.0.0.1:8000',
      '/departments': 'http://127.0.0.1:8000',
      '/query': 'http://127.0.0.1:8000',
    },
  },
})

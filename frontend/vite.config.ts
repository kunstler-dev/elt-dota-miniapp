import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // locally the frontend runs on :5173, the API is uvicorn on :8000
    proxy: { '/api': 'http://localhost:8000' },
  },
})

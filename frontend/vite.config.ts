import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const BACKEND_URL = process.env.MUSIC_TRAINER_BACKEND_URL ?? 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // during development the backend runs separately; forward API calls to it
    proxy: { '/api': BACKEND_URL },
  },
  test: {
    include: ['src/**/*.test.ts'],
  },
})

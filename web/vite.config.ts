/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/OwlPath/',
  // The app imports the dataset from ../data at the repo root.
  server: { fs: { allow: ['..'] } },
  test: { environment: 'node', include: ['src/**/*.test.ts', 'scripts/**/*.test.ts'] },
})

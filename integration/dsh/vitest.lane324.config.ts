import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    include: ['lane324_kc_roundtrip.e2e.ts'],
    testTimeout: 300_000,
    hookTimeout: 300_000,
    pool: 'forks',
  },
})

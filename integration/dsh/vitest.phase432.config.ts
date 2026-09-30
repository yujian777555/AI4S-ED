import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    include: ['lane325_kc_evidence_roundtrip.e2e.ts'],
    testTimeout: 300_000,
    hookTimeout: 300_000,
    pool: 'forks',
  },
})

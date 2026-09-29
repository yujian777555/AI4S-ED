/**
 * Vitest config for Phase 4.3.1 lane325 mounted evidence roundtrip.
 * Run from anywhere with DSH_SRC pointing at the pinned DSH checkout:
 *   pnpm exec vitest run --config <this file>
 */
import { defineConfig } from 'vitest/config'
import { resolve } from 'node:path'

const DSH_SRC = process.env.DSH_SRC
if (!DSH_SRC) throw new Error('DSH_SRC env var is required')
const HERE = resolve(import.meta.dirname ?? '.')

export default defineConfig({
  root: DSH_SRC,
  test: {
    root: DSH_SRC,
    include: [resolve(HERE, 'lane325_kc_evidence_roundtrip.e2e.ts')],
    testTimeout: 300_000,
    hookTimeout: 300_000,
    pool: 'forks',
    server: {
      deps: {
        moduleDirectories: ['node_modules', resolve(DSH_SRC, 'node_modules')],
      },
    },
  },
})

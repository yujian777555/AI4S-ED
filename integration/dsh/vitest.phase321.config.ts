import { defineConfig } from 'vitest/config'
import { resolve } from 'node:path'

const DSH_SRC = process.env.DSH_SRC
if (!DSH_SRC) throw new Error('DSH_SRC env var is required')
const HERE = resolve(import.meta.dirname ?? '.')

export default defineConfig({
  root: DSH_SRC,
  test: {
    root: DSH_SRC,
    include: [resolve(HERE, 'phase321_preset_smoke.ts')],
    testTimeout: 180_000,
    hookTimeout: 180_000,
    pool: 'forks',
    server: {
      deps: {
        moduleDirectories: ['node_modules', resolve(DSH_SRC, 'node_modules')],
      },
    },
  },
  resolve: {
    alias: {
      // ensure workspace packages resolve from the pinned checkout
    },
  },
})

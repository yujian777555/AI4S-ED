/**
 * Extend the pinned DSH web vitest config with the Phase 3.2.1 smoke file.
 * Run from DSH_SRC:
 *   pnpm exec vitest run --config <this file>
 */
import { mergeConfig } from 'vitest/config'
// @ts-expect-error resolving from DSH_SRC node_modules at runtime
import webConfig from 'C:/dsh-src/vitest.web.config.ts'

export default mergeConfig(webConfig, {
  test: {
    include: [
      ...(webConfig.test?.include ?? []),
      'C:/Users/于舰/XiaomiMiMoProjects/AI4S-ED/integration/dsh/phase321_preset_smoke.e2e.ts',
    ],
    testTimeout: 180_000,
  },
})

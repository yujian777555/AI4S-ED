/**
 * Register hooks that stub `vitest` when scaffold is imported outside a worker.
 */
import { register } from 'node:module'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const dir = dirname(fileURLToPath(import.meta.url))
register(pathToFileURL(join(dir, 'vitest-stub-hooks.mjs')).href, pathToFileURL(import.meta.url))

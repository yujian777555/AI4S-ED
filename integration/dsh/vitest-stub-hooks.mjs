import { pathToFileURL } from 'node:url'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const STUB = pathToFileURL(join(dirname(fileURLToPath(import.meta.url)), 'vitest-stub.mjs')).href

export async function resolve(specifier, context, next) {
  if (specifier === 'vitest' || specifier.startsWith('vitest/')) {
    return { shortCircuit: true, url: STUB }
  }
  return next(specifier, context)
}

/**
 * Minimal vitest stub so scaffold.ts can import outside a vitest runner.
 */
export function expect() {
  return {
    toBe: () => undefined,
    toEqual: () => undefined,
    toContain: () => undefined,
    toBeDefined: () => undefined,
    toBeUndefined: () => undefined,
    toBeTruthy: () => undefined,
    toBeFalsy: () => undefined,
    toHaveLength: () => undefined,
  }
}
export function describe() {}
export function it() {}
export function test() {}
export function beforeAll() {}
export function afterAll() {}
export function beforeEach() {}
export function afterEach() {}
export function onTestFailed() {}
export function vi() {
  return { fn: () => () => undefined, mock: () => undefined }
}
export default { expect, describe, it, test, beforeAll, afterAll, beforeEach, afterEach, vi, onTestFailed }

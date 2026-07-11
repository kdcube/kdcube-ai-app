/**
 * Minimal ambient typings for the node built-ins the feature tests use.
 * The widget compiles its tests with the browser-targeted tsconfig (no
 * @types/node); the tests run under plain `node --test`.
 */
declare module 'node:assert/strict' {
  interface StrictAssert {
    (value: unknown, message?: string): void
    equal(actual: unknown, expected: unknown, message?: string): void
    deepEqual(actual: unknown, expected: unknown, message?: string): void
    ok(value: unknown, message?: string): void
  }
  const assert: StrictAssert
  export default assert
}

declare module 'node:test' {
  export function test(name: string, fn: () => void | Promise<void>): void
}

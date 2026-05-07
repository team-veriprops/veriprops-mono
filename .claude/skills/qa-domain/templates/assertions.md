# Template: assertions.ts

## Purpose

Domain-specific assertion functions used in `journeys.ts` step `assertion` fields. Each function tests one specific, named condition and returns an `AssertionResult`. They never throw.

## Core rule

**Assertions never throw.** Every code path must return an `AssertionResult` with `status: "pass"`, `"fail"`, or `"skip"`. If an internal operation might throw (e.g. a DOM lookup), wrap it in try/catch and return a fail result.

The flow engine converts assertion failures into step failures, captures forensic artifacts, and emits events. It cannot do this if the assertion throws unexpectedly.

## Naming convention

`assert` + Subject (noun) + Condition (adjective or verb phrase)

Good names:
- `assertLoginPageLoaded`
- `assertOrderCreated`
- `assertUserIsRedirectedToDashboard`
- `assertEmailReceived`
- `assertProductInCart`

Bad names:
- `check`
- `testThing`
- `assertTrue`
- `assertStep3`

## Using core helpers

Always import from `../../core/assertions.js`. Do not re-implement helpers that already exist.

Available helpers:
- HTTP: `assertStatus`, `assertStatusOk`, `assertBodyKey`, `assertBodySchema`, `assertHeader`
- URL: `assertUrlContains`, `assertUrlEquals`
- DOM: `assertElementVisible`, `assertElementText`, `assertElementCount`
- Email: `assertEmailReceived`, `assertEmailCount`
- Generic: `assertEqual`, `assertTruthy`, `assertDefined`, `skipAssertion`

## Composition pattern

Chain multiple checks by returning early on the first failure:

```typescript
export async function assertCheckoutComplete(page: Page): Promise<AssertionResult> {
  const urlCheck = assertUrlContains(page, "/order-confirmation");
  if (urlCheck.status === "fail") return urlCheck;

  const elementCheck = await assertElementVisible(page, "[data-testid='order-id']");
  if (elementCheck.status === "fail") return elementCheck;

  return assertElementVisible(page, "[data-testid='confirmation-email-notice']");
}
```

This surfaces the first failure with its specific message, making debugging faster.

## Parameters

Assertions that need live data accept it as parameters — they never fetch internally.

```typescript
// Good — data fetched by the journey, passed in
export function assertProductExists(
  response: APIResponse<{ products: Array<{ id: string }> }>
): AssertionResult { ... }

// Bad — fetches internally, hides errors, hard to test
export async function assertProductExists(): Promise<AssertionResult> {
  const response = await fetch("/api/products"); // ← never do this
  ...
}
```

## When to use skipAssertion

Use `skipAssertion(reason)` when:
- The assertion cannot run because a prerequisite step was skipped
- The condition is not applicable for this environment (e.g. an email assertion in static OTP mode)

```typescript
if (config.otpMode === "static") {
  return skipAssertion("Email assertion skipped — OTP_MODE is static");
}
```

## What NOT to put here

- Playwright API calls outside of the assertion helper functions (use the helpers which accept `Page` as a param)
- Network requests or database queries
- Step sequencing logic — that belongs in `journeys.ts`
- State mutations — assertions are read-only
- Business logic that belongs in the application itself

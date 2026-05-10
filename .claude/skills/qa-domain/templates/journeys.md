# Template: journeys.ts

## Purpose

Defines the user flows this domain exercises. Each journey is a named sequence of steps that tests one complete interaction path from start to finish.

## Journey design principles

**One flow per journey.** A journey should test one thing completely. "User logs in and then creates an order and then views the receipt" is three journeys, not one.

**Name as verb phrases.** The name is shown in reports and logs. It should be readable by a non-engineer. Good: `"customer completes checkout with saved card"`. Bad: `"test_checkout_flow_2"`.

**Happy path first.** Generate the happy path journey before edge cases. The happy path is the most valuable — it exercises the entire flow end-to-end.

**Browser vs API.** Use `mode: "browser"` when the flow involves UI interaction. Use `mode: "api"` when testing backend behaviour that does not require a browser (CRUD endpoints, business logic, data validation).

## Step types reference

| Type | What it does | Required fields |
|---|---|---|
| `navigate` | Navigate to a URL | `url` |
| `click` | Click an element | `selector` |
| `fill` | Type into an input | `selector`, `value` |
| `select` | Choose a dropdown option | `selector`, `value` |
| `wait` | Pause execution | `duration` (ms) |
| `wait-for-selector` | Wait for element to appear | `selector` |
| `wait-for-network` | Wait for network idle | — |
| `assert` | Run an assertion function | `assertion` |
| `screenshot` | Capture a manual screenshot | — |
| `api-call` | Make an HTTP request | `apiOptions` |
| `custom` | Run arbitrary logic | `handler` |

## Selector rules

- `selector` fields must be keys from `selectors.ts` — never raw CSS strings
- If you need a selector not in `selectors.ts`, add it there first
- The flow engine logs a warning when a selector key is not found in the map and falls back to treating it as a raw string — eliminate these warnings

## Value interpolation

Both `value` and `url` fields support `{{path}}` token interpolation:

- `{{config.baseUrl}}` — the frontend base URL from QAConfig
- `{{config.apiBaseUrl}}` — the backend API base URL
- `{{state.someKey}}` — a value stored in `ctx.state` by a previous step

When a token resolves to `undefined`, the flow engine logs a structured warning with the step name, field name, and the missing path. Check that the state key is set by a prior step.

## Storing values between steps

Use `type: "custom"` with a `handler` to read and write `ctx.state`:

```typescript
{
  type: "custom",
  label: "Extract order ID from URL",
  handler: async (ctx) => {
    const url = ctx.state["__currentUrl"] as string ?? "";
    const match = url.match(/\/orders\/([a-z0-9-]+)/);
    if (match?.[1]) ctx.state["orderId"] = match[1];
  },
}
```

Then reference it in a later step: `value: "{{state.orderId}}"`.

## API call results

After a step with `type: "api-call"`, the response is stored at:
`ctx.state["__apiResponse_<step label>"]`

Access it in a subsequent `assert` step via a custom assertion or `custom` handler.

## optional flag

Mark a step `optional: true` when its failure should not cascade to subsequent steps. Use for:
- Dismissing optional modals or cookie banners that may or may not appear
- Steps that are nice-to-have but not required for the main flow

Do not overuse — optional steps can mask real failures.

## skip flag on journeys

Add `skip: true` to a journey during active development to prevent it from running. Remove it before merging. The journey will appear as "skip" in the report.

## What NOT to put in journeys

- Direct Playwright API calls (use `type: "custom"` with the handler receiving `ctx`, not `page` directly — `page` is managed by the runner)
- Raw CSS selector strings in `selector` fields
- Hardcoded test data — put it in `fixtures.ts` payloads or read from `ctx.state`
- Assertion logic — use `type: "assert"` with a function from `assertions.ts`

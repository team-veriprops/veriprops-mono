# Template: selectors.ts

## Purpose

A flat key-value map from logical selector names to CSS or XPath selector strings. Every interactive element in every browser journey must have an entry here. Journey steps reference keys from this map — never raw selector strings.

This centralisation means: when the UI changes, you update one file, not every journey that uses that element.

## Rules

### Selector preference order

1. **`data-testid` attributes** — most stable; not affected by styling or structural changes
2. **`id` attributes** — stable if the team uses semantic IDs consistently
3. **ARIA roles and labels** — `[role="button"][aria-label="Submit"]` — good for accessibility-tested UIs
4. **Semantic HTML** — `form > button[type="submit"]` — acceptable when specific
5. **Class names** — only if they are utility-free semantic class names (`.checkout-form`, not `.mt-4.flex`)
6. **Positional selectors** — `:nth-child`, `:first-child` — avoid entirely; they break on UI changes

### Naming convention

Keys must be camelCase and self-documenting. The name should describe the element's role, not its appearance.

Good: `checkoutSubmitButton`, `emailInputField`, `errorBannerText`, `navProfileLink`
Bad: `button1`, `redBox`, `firstInput`, `el`

### Grouping

Group selectors by page or section using comment blocks:

```typescript
// ── Login page ────────────────────────────────────────────────
emailInput: "[data-testid='login-email']",
passwordInput: "[data-testid='login-password']",
submitButton: "[data-testid='login-submit']",

// ── Dashboard ─────────────────────────────────────────────────
dashboardWelcome: "[data-testid='dashboard-welcome']",
```

### Missing data-testid attributes

When a required element has no `data-testid`:
1. Use the best available fallback selector
2. Add a `// TODO:` comment above the entry:
   ```typescript
   // TODO: Add data-testid='checkout-total' to <OrderSummary> component
   checkoutTotal: ".order-summary__total",
   ```
3. Note it in the domain README under "Known limitations"

Do not block domain generation waiting for `data-testid` additions — generate with fallbacks and file the TODO.

### API-only domains

If the domain has no browser journeys, export an empty object:

```typescript
export const selectors: SelectorMap = {};
```

Do not omit the export — the runtime expects it.

### What NOT to include

- Selectors for elements the domain never interacts with
- XPath selectors unless there is genuinely no CSS alternative
- Selectors with hardcoded test data values (`[data-testid='user-John']`)
- Dynamic selectors built with string interpolation — use `type: "custom"` steps with `ctx.state` for dynamic targeting

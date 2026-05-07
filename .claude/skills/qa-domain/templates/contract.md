# Template: contract.ts

## Purpose

Declares the domain's identity and runtime behaviour flags. This is the first file the runtime reads when loading a domain. It is also the file the `validate` command checks for schema compatibility.

## Rules

### schemaVersion
Always set to `CURRENT_SCHEMA_VERSION` imported from `../../core/types.js`. Never hardcode the version string — always import the constant. This ensures the domain is stamped with the version at generation time and the registry can detect drift later.

### name
Must be kebab-case. Must exactly match:
- The directory name under `qa/domains/`
- The key in `domain-manifest.json`
- The `name` field in the manifest entry

If any of these three do not match, validation fails and the domain will not load.

### description
One sentence describing what user flows this domain covers. Shown in run reports and CLI output. Keep it under 100 characters.

### dependsOn
An array of domain `name` strings. Only populate when this domain genuinely cannot run successfully unless another domain has already run (e.g. it depends on data that another domain seeds, or a user account that another domain creates).

Do not use `dependsOn` as a way to sequence unrelated domains — it creates fragility. If domains are truly independent, leave the array empty.

The orchestrator performs a topological sort on `dependsOn` before execution. Circular dependencies are detected and block the run.

### otpPattern
Optional. Provide only when:
1. The domain has flows that involve OTP extraction from email, AND
2. The default pattern `\b\d{4,8}\b` would match the wrong number (e.g. the email body contains many other digit sequences)

Format: a JavaScript regex source string with exactly one capture group containing the OTP digits.

Example: `"Your verification code is (\\d{6})"` — note the double-escaped backslash since it is a string, not a regex literal.

If provided and the string cannot be compiled to a valid RegExp, the adapter falls back to the default pattern with a warning.

### appReadySelector
Optional. Provide only when:
1. The domain has browser journeys, AND
2. The application does not set `window.__app_ready = true`, AND
3. There is a stable CSS selector that reliably indicates the page is fully interactive

Resolution priority: domain contract → QAConfig.appReadySelector → `window.__app_ready` → networkidle fallback.

### tags
Lowercase kebab-case strings. Use existing tags from other domains for consistency. Common tags: `auth`, `payments`, `onboarding`, `admin`, `customer`, `api-only`.

### owner
A team name, GitHub team slug, or email address. Used in drift reports to route stale domain notifications. Check `CODEOWNERS` or `package.json#maintainers` for the right value.

## What NOT to put here

- No logic, no functions, no imports beyond `CURRENT_SCHEMA_VERSION` and `DomainContract`
- No selectors, steps, or fixture data
- No comments explaining the application — that belongs in README.md

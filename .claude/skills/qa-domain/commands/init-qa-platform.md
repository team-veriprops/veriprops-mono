# Command: /qa init-qa-platform

Sets up the QA platform for first use in this repository.

## When to use

Run once after cloning a new repository or after the `qa/` directory has been freshly added to an existing monorepo.

## Pre-conditions

- `qa/` directory exists with `package.json` and `tsconfig.json`
- `qa/.env.example` exists
- User has access to run terminal commands

## Steps

1. **Read** `SKILL.md` fully before proceeding.

2. **Verify platform files exist:**
   ```bash
   ls qa/core/types.ts qa/domain-manifest.json qa/.env.example
   ```
   If any are missing, report which files are absent and stop.

3. **Check for existing .env:**
   ```bash
   ls qa/.env 2>/dev/null && echo "exists" || echo "missing"
   ```
   If missing, instruct the user:
   > Copy `qa/.env.example` to `qa/.env` and fill in the values for your local environment before running `pnpm qa:init`.

4. **Check pnpm is available:**
   ```bash
   which pnpm && pnpm --version
   ```
   If not available, instruct the user to install it.

5. **Install dependencies:**
   ```bash
   cd qa && pnpm install
   ```

6. **Run platform init:**
   ```bash
   cd qa && pnpm qa:init
   ```
   Report the output. If connectivity checks fail, explain which services need to be running.

7. **Run typecheck:**
   ```bash
   cd qa && pnpm typecheck
   ```
   If typecheck fails, report the errors. Do not proceed until typecheck passes.

8. **Summary:** Report what was set up, what passed, and what (if anything) needs manual action.

## Success criteria

- `pnpm qa:init` exits 0
- `pnpm typecheck` exits 0
- `qa/domain-manifest.json` exists and is valid JSON
- `qa/artifacts/` directory exists

## Common issues

**`BASE_URL not set`** — `.env` file is missing or incomplete. Instruct user to copy `.env.example`.

**Backend not reachable** — Service is not running. Instruct user to start their local dev stack before running QA.

**TypeScript errors** — Usually caused by a Node.js version mismatch. Verify Node >= 20.

// ─────────────────────────────────────────────────────────────────────────────
// domains/[DOMAIN_NAME]/assertions.ts
// [CLAUDE: Domain-specific assertion factories used in journeys.ts steps.]
// [CLAUDE: Import helpers from core/assertions.ts — do not re-implement them.]
// [CLAUDE: Every function here must return AssertionResult — never throw.]
// [CLAUDE: Name functions as "assert" + subject + condition, e.g. assertUserIsLoggedIn.]
// [CLAUDE: Functions that need a Page or APIResponse accept them as parameters.]
// ─────────────────────────────────────────────────────────────────────────────

import type { Page } from "@playwright/test";
import type { APIResponse, AssertionResult } from "../../core/types.js";
import {
  assertUrlContains,
  assertElementVisible,
  assertElementText,
  assertStatus,
  assertBodyKey,
  assertEqual,
  assertDefined,
  skipAssertion,
} from "../../core/assertions.js";

// [CLAUDE: Export one assertion function per testable condition in this domain.]
// [CLAUDE: Use the imported helpers above as building blocks.]
// [CLAUDE: If an assertion requires live data (API call, email), accept the
//          data as a parameter — do not fetch inside the assertion function.]

// [CLAUDE: Example browser assertion — replace with real domain assertions:]
export async function assert[FeatureName]PageLoaded(page: Page): Promise<AssertionResult> {
  // [CLAUDE: Replace "/expected-route" and "[data-testid='...']" with real values.]
  const urlCheck = assertUrlContains(page, "/[expected-route]");
  if (urlCheck.status === "fail") return urlCheck;

  return assertElementVisible(page, "[data-testid='[key-element]']");
}

// [CLAUDE: Example API assertion — replace with real domain assertions:]
export function assert[ResourceName]Created(
  response: APIResponse<{ id?: string; [key: string]: unknown }>
): AssertionResult {
  const statusCheck = assertStatus(response, 201);
  if (statusCheck.status === "fail") return statusCheck;

  return assertBodyKey(response as APIResponse<Record<string, unknown>>, "id");
}

// [CLAUDE: Add more assertion functions below. Each should test one specific condition.]
// [CLAUDE: Remove the example functions above once you have real assertions.]

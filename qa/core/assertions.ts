// ─────────────────────────────────────────────────────────────────────────────
// core/assertions.ts
// Pure assertion helpers used in domain assertions.ts and journey steps.
// All functions return AssertionResult — they never throw.
// ─────────────────────────────────────────────────────────────────────────────

import type { APIResponse, AssertionResult } from "./types.js";
import type { Page } from "@playwright/test";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function pass(message: string): AssertionResult {
  return { status: "pass", message };
}

function fail(message: string, actual?: unknown, expected?: unknown): AssertionResult {
  return { status: "fail", message, actual, expected };
}

export function skipAssertion(reason: string): AssertionResult {
  return { status: "skip", message: reason };
}

// ─── HTTP Assertions ─────────────────────────────────────────────────────────

export function assertStatus(
  response: APIResponse,
  expected: number
): AssertionResult {
  if (response.status === expected) {
    return pass(`Status is ${expected}`);
  }
  return fail(`Expected status ${expected}`, response.status, expected);
}

export function assertStatusOk(response: APIResponse): AssertionResult {
  if (response.ok) return pass(`Status ${response.status} is OK`);
  return fail(`Expected OK status (2xx)`, response.status, "2xx");
}

export function assertBodyKey<T = unknown>(
  response: APIResponse<Record<string, T>>,
  key: string,
  expected?: T
): AssertionResult {
  const body = response.body;
  if (!(key in body)) {
    return fail(`Response body missing key "${key}"`, Object.keys(body), key);
  }
  if (expected !== undefined && body[key] !== expected) {
    return fail(`body["${key}"] mismatch`, body[key], expected);
  }
  return pass(`body["${key}"] ${expected !== undefined ? `=== ${String(expected)}` : "exists"}`);
}

export function assertBodySchema(
  response: APIResponse,
  requiredKeys: string[]
): AssertionResult {
  const body = response.body as Record<string, unknown>;
  const missing = requiredKeys.filter((k) => !(k in body));
  if (missing.length > 0) {
    return fail(`Response body missing keys: ${missing.join(", ")}`, Object.keys(body), requiredKeys);
  }
  return pass(`Response body contains all required keys: ${requiredKeys.join(", ")}`);
}

export function assertHeader(
  response: APIResponse,
  header: string,
  expected?: string
): AssertionResult {
  const value = response.headers[header.toLowerCase()];
  if (value === undefined) {
    return fail(`Response missing header "${header}"`, undefined, expected ?? "<any>");
  }
  if (expected !== undefined && value !== expected) {
    return fail(`Header "${header}" mismatch`, value, expected);
  }
  return pass(`Header "${header}" ${expected !== undefined ? `=== "${expected}"` : "present"}`);
}

// ─── URL Assertions ───────────────────────────────────────────────────────────

export function assertUrlContains(page: Page, substring: string): AssertionResult {
  const url = page.url();
  if (url.includes(substring)) return pass(`URL contains "${substring}"`);
  return fail(`URL does not contain "${substring}"`, url, substring);
}

export function assertUrlEquals(page: Page, expected: string): AssertionResult {
  const url = page.url();
  if (url === expected) return pass(`URL === "${expected}"`);
  return fail(`URL mismatch`, url, expected);
}

// ─── DOM Assertions ───────────────────────────────────────────────────────────

export async function assertElementVisible(
  page: Page,
  selector: string,
  timeoutMs = 5000
): Promise<AssertionResult> {
  try {
    await page.waitForSelector(selector, { state: "visible", timeout: timeoutMs });
    return pass(`Element "${selector}" is visible`);
  } catch {
    return fail(`Element "${selector}" not visible within ${timeoutMs}ms`, selector);
  }
}

export async function assertElementText(
  page: Page,
  selector: string,
  expected: string,
  timeoutMs = 5000
): Promise<AssertionResult> {
  try {
    await page.waitForSelector(selector, { timeout: timeoutMs });
    const actual = await page.textContent(selector);
    if (actual?.trim() === expected) {
      return pass(`Element "${selector}" text === "${expected}"`);
    }
    return fail(`Element "${selector}" text mismatch`, actual?.trim(), expected);
  } catch {
    return fail(`Element "${selector}" not found within ${timeoutMs}ms`);
  }
}

export async function assertElementCount(
  page: Page,
  selector: string,
  expected: number
): Promise<AssertionResult> {
  const count = await page.locator(selector).count();
  if (count === expected) return pass(`Found ${expected} element(s) matching "${selector}"`);
  return fail(`Element count mismatch for "${selector}"`, count, expected);
}

// ─── Email Assertions ─────────────────────────────────────────────────────────

export function assertEmailReceived(
  emails: unknown[],
  subjectContains: string
): AssertionResult {
  const found = (emails as Array<{ Subject?: string }>).some((e) =>
    e.Subject?.includes(subjectContains)
  );
  if (found) return pass(`Email with subject containing "${subjectContains}" received`);
  return fail(`No email with subject containing "${subjectContains}" found`, emails.length, ">0");
}

export function assertEmailCount(
  emails: unknown[],
  expected: number
): AssertionResult {
  if (emails.length === expected) return pass(`Received ${expected} email(s)`);
  return fail(`Email count mismatch`, emails.length, expected);
}

// ─── Generic Assertions ───────────────────────────────────────────────────────

export function assertEqual<T>(actual: T, expected: T, label?: string): AssertionResult {
  if (actual === expected) {
    return pass(label ?? `Values are equal: ${String(actual)}`);
  }
  return fail(label ?? `Values not equal`, actual, expected);
}

export function assertTruthy(value: unknown, label?: string): AssertionResult {
  if (value) return pass(label ?? `Value is truthy`);
  return fail(label ?? `Value is falsy`, value, "truthy");
}

export function assertDefined(value: unknown, label?: string): AssertionResult {
  if (value !== undefined && value !== null) {
    return pass(label ?? `Value is defined`);
  }
  return fail(label ?? `Value is null or undefined`, value, "defined");
}

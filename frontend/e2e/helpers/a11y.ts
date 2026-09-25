/**
 * Accessibility assertion applied to every covered page/state (docs/uat-strategy.md §7).
 *
 * A11y is a first-class acceptance criterion, not a separate pass: no serious/critical
 * axe violation is a pass condition of the scenario itself. Pre-existing debt is held in
 * an explicit, tracked baseline (`A11Y_BASELINE`) so the suite can go green while the
 * debt is burned down deliberately rather than silently suppressed — every entry needs a
 * reason and an owner, and removing entries is the point.
 */
import AxeBuilder from "@axe-core/playwright";
import { Page, expect } from "@playwright/test";

/** Only these impact levels fail a scenario; minor/moderate are reported, not blocking. */
const BLOCKING_IMPACTS = new Set(["serious", "critical"]);

/** WCAG 2.1 A/AA — the agreed ruleset for acceptance. */
const RULESET = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

/**
 * Known pre-existing violations, keyed by axe rule id, with the reason they are not yet
 * fixed. Time-boxed: each entry is debt to burn down, never a permanent exemption.
 */
const A11Y_BASELINE: Record<string, string> = {};

/**
 * Sonner's toast list. Page scans leave it out: a toast lives ~4 s and can start fading while a
 * scan runs, and axe then reads a blended colour neither state has (2.19:1 mid-fade vs ~17:1 at
 * rest). Toasts are checked once, deliberately, at rest — `UAT-WA-04` scans a settled toast with
 * `include: TOASTER_SELECTOR`. Every toast shares one Sonner style, so that one check covers them.
 */
export const TOASTER_SELECTOR = "[data-sonner-toaster]";

export interface A11yOptions {
  /** Restrict the scan to a container (e.g. an open dialog) instead of the whole page. */
  include?: string;
  /** Rule ids to skip for this call only — justify inline at the call site. */
  disableRules?: string[];
}

/**
 * Assert *page* has no blocking accessibility violations outside the tracked baseline.
 * Call it on every page state a scenario visits.
 */
export async function expectNoA11yViolations(page: Page, options: A11yOptions = {}): Promise<void> {
  // Axe reads computed colours, so a scan taken mid-transition (a disabled button fading in
  // over 200ms, a dialog easing open) reports blended, failing contrast that neither the start
  // nor the end state has. Wait for finite animations and transitions to finish; endless ones
  // (a spinner) are left running.
  await page.waitForFunction(() =>
    document
      .getAnimations()
      .every((a) => a.playState !== "running" || a.effect?.getTiming().iterations === Infinity),
  );

  let builder = new AxeBuilder({ page }).withTags(RULESET);
  if (options.include) builder = builder.include(options.include);
  // Toasts are left out of every scan except one aimed at them (see TOASTER_SELECTOR).
  if (options.include !== TOASTER_SELECTOR) builder = builder.exclude(TOASTER_SELECTOR);

  const skipped = [...Object.keys(A11Y_BASELINE), ...(options.disableRules ?? [])];
  if (skipped.length) builder = builder.disableRules(skipped);

  const { violations } = await builder.analyze();
  const blocking = violations.filter((violation) => BLOCKING_IMPACTS.has(violation.impact ?? ""));

  expect(
    blocking,
    `Accessibility violations on ${page.url()}:\n${formatViolations(blocking)}`,
  ).toEqual([]);
}

function formatViolations(violations: { id: string; help: string; nodes: { html: string }[] }[]) {
  return violations
    .map((violation) => {
      const nodes = violation.nodes.map((node) => `      ${node.html}`).join("\n");
      return `  • ${violation.id} — ${violation.help}\n${nodes}`;
    })
    .join("\n");
}

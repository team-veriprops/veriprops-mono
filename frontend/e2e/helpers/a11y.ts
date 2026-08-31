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
  let builder = new AxeBuilder({ page }).withTags(RULESET);
  if (options.include) builder = builder.include(options.include);

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

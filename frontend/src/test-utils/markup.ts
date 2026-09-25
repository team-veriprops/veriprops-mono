/**
 * Assertions about rendered markup, shared by the component tests that check a control is
 * actually reachable rather than merely present.
 *
 * These read the *whole tag* carrying a given `data-testid`, because a page renders many
 * controls and the first `id=` in the document is rarely the one under test — and because
 * React makes no promise about the order it writes attributes in.
 */

/** The rendered tag carrying `data-testid="<testId>"`, or "" when nothing does. */
export function tagFor(html: string, testId: string): string {
  return new RegExp(`<[^>]*data-testid="${testId}"[^>]*>`).exec(html)?.[0] ?? "";
}

/** The value of *attribute* on the tag carrying *testId*, or null when it has none. */
export function attributeFor(html: string, testId: string, attribute: string): string | null {
  return new RegExp(`\\s${attribute}="([^"]*)"`).exec(tagFor(html, testId))?.[1] ?? null;
}

/**
 * Whether the control carrying *testId* has an accessible name: either a `<label for>` bound
 * to its id, or a non-empty `aria-label` of its own. A label that only sits next to a control
 * names nothing (axe `label` / `button-name`, both critical).
 */
export function isNamed(html: string, testId: string): boolean {
  if (attributeFor(html, testId, "aria-label")) return true;
  const id = attributeFor(html, testId, "id");
  return !!id && new RegExp(`<label[^>]*\\sfor="${id}"`).test(html);
}

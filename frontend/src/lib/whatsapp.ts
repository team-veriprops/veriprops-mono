/**
 * WhatsApp channel attribution (PRD §7.4.1, §7.10).
 *
 * The widget deep-links out to the official number with a prefilled greeting carrying a
 * page code, so an enquiry can be attributed to the page it started from — the
 * "WhatsApp-attributed enquiries" metric. The number itself is **not** here: it is
 * backend-owned and arrives via `/config/public`, because it is also published on
 * certified reports and in investor materials and must never drift between surfaces
 * (§7.1.2). Page codes, by contrast, describe *frontend* routes the backend does not
 * model, so they are derived from the route registry.
 */
import { PAYMENT_FLOW_PATH_PATTERNS, ROUTES } from "./routes";

/** Opening line of every widget-originated chat. The bot greets back on first contact. */
export const WHATSAPP_PREFILL_GREETING = "Hi Veriprops!";

/** Pages whose attribution code is worth naming rather than deriving. */
const EXPLICIT_PAGE_CODES: Readonly<Record<string, string>> = {
  [ROUTES.HOME]: "web-home",
  // The PRD names this code directly (§7.4.1).
  [ROUTES.SAMPLE_REPORT]: "web-report-sample",
  // Enquiry → intake-started is its own funnel step (§7.10), so intake is not just
  // another portal page.
  [ROUTES.PORTAL.VERIFICATIONS_NEW]: "web-intake",
};

/** First path segment → code, for the surfaces where one code per area is enough. */
const SEGMENT_PAGE_CODES: Readonly<Record<string, string>> = {
  portal: "web-portal",
};

function normalizePath(pathname: string): string {
  const withoutQuery = (pathname || "").split(/[?#]/, 1)[0];
  const trimmed = withoutQuery.replace(/\/+$/, "");
  return trimmed || ROUTES.HOME;
}

/**
 * The attribution code for a page. Explicit entries win; anything else derives from the
 * first path segment, so a newly added page stays attributable without a table edit.
 */
export function pageCodeFor(pathname: string): string {
  const path = normalizePath(pathname);
  const explicit = EXPLICIT_PAGE_CODES[path];
  if (explicit) return explicit;

  const segment = path.split("/")[1] ?? "";
  const mapped = SEGMENT_PAGE_CODES[segment];
  if (mapped) return mapped;

  // The code travels through WhatsApp message text and back out of the bot's parser,
  // so reduce it to a safe token rather than trusting the raw segment.
  const slug = decodeURIComponent(segment)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug ? `web-${slug}` : "web-home";
}

/**
 * The `wa.me` deep link for a page code. Returns an empty string when no number is
 * configured yet — callers render nothing rather than falling back to a hardcoded
 * number, which would defeat the §7.1.2 single-source rule.
 */
export function waMeUrl(numberDigits: string, pageCode: string): string {
  if (!numberDigits) return "";
  const text = encodeURIComponent(`${WHATSAPP_PREFILL_GREETING} [ref: ${pageCode}]`);
  return `https://wa.me/${numberDigits}?text=${text}`;
}

/** True inside a payment flow, where the widget stays hidden (§7.4.1). */
export function isPaymentFlowPath(pathname: string): boolean {
  const path = normalizePath(pathname);
  return PAYMENT_FLOW_PATH_PATTERNS.some((pattern) => pattern.test(path));
}

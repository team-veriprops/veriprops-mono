/**
 * Client-side operational constants.
 *
 * Kept in one place so pagination defaults, poll cadence, SSE reconnect behaviour,
 * upload caps, and the default dial code stay consistent app-wide instead of being
 * duplicated as magic numbers across components and service files. Backend remains
 * the source of truth for anything it owns (e.g. the chat message cap arrives via
 * /config/public); these are request-side defaults and pure client UX tuning.
 */

// ── Pagination (request-side page-size defaults; server owns the response) ──
export const DEFAULT_PAGE_SIZE = 10;
export const DEFAULT_HISTORY_PAGE_SIZE = 20;
export const CHAT_MESSAGES_PAGE_SIZE = 30;

// ── SSE reconnect (useUserStream / useVerificationStream) ──
export const SSE_MAX_RETRIES = 3;
export const SSE_BASE_BACKOFF_MS = 1000;

// ── TanStack Query cadence (poll fallback + staleness) ──
export const REFETCH_INTERVAL_MS = 60_000;
export const SHORT_REFETCH_INTERVAL_MS = 30_000;
export const STALE_TIME_MS = 60_000;
export const SHORT_STALE_TIME_MS = 30_000;
export const LONG_STALE_TIME_MS = 5 * 60_000;

// ── Phone / locale ──
export const DEFAULT_DIAL_CODE = "+234";

// ── Brand contact (customer-facing support address) ──
export const SUPPORT_EMAIL = "support@veriprops.ng";

// ── Upload caps (bytes) ──
export const UPLOAD_MAX_IMAGE_SIZE = 10 * 1024 * 1024; // 10 MB
export const UPLOAD_MAX_PDF_SIZE = 20 * 1024 * 1024; // 20 MB
export const UPLOAD_MAX_VIDEO_SIZE = 100 * 1024 * 1024; // 100 MB

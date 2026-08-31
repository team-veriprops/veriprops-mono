import { AuthIntent } from "@/components/website/auth/models";

export const ROUTES = {
  HOME: '/',

  AUTH: {
    GATE: '/auth',
    LOGIN: '/auth/login',
    SIGNUP: '/auth/signup',
    FORGOT_PASSWORD: '/auth/forgot-password',
    RESET_PASSWORD: (token: string) => `/auth/reset-password/${token}`,
    SET_PASSWORD: '/auth/set-password',
    OAUTH_CALLBACK: (provider: string) => `/auth/oauth/${provider}/callback`,
    OAUTH_ERROR: '/auth/oauth/error',
    LOGIN_SUCCESS_REDIRECT: "/auth/login/success-redirect"
  },

  ACCOUNT: {
    ROOT: '/account',
    SECURITY: '/account/security',
    DEVICES: '/account/devices',
    LINKED: '/account/linked',
    PASSWORD: '/account/password',
    CONSENTS: '/account/consents',
    DATA_PRIVACY: '/account/data-privacy',
  },

  AGENT: {
    GATE: '/agents',
    DASHBOARD: '/agents/dashboard',
    APPLY: '/agents/apply',
    TASKS: '/agents/tasks',
    TASK_DETAIL: (taskId: string) => `/agents/tasks/${taskId}`,
    TASK_HISTORY: (taskId: string) => `/agents/tasks/${taskId}/history`,
    TASK_MESSAGES: (taskId: string) => `/agents/tasks/${taskId}/messages`,
    EARNINGS: '/agents/earnings',
    PAYOUTS: '/agents/payouts',
    DISPUTES: '/agents/disputes',
    PROFILE: '/agents/profile',
    SETTINGS_COVERAGE: '/agents/settings/coverage',
    NOTIFICATION_PREFERENCES: '/agents/account/notification-preferences',
  },
  ADMIN: {
    GATE: '/admin',
    DASHBOARD: '/admin/dashboard',
    TEAM: '/admin/team',
    USERS: '/admin/users',
    USER_DETAIL: (uid: string) => `/admin/users/${uid}`,
    AGENT_APPLICATIONS: '/admin/agents/applications',
    INVITE_ACCEPT: (token: string) => `/auth/admin-invite/${token}`,
    VERIFICATIONS: '/admin/verifications',
    VERIFICATION_DETAIL: (vid: string) => `/admin/verifications/${vid}`,
    VERIFICATION_MESSAGES: (vid: string) => `/admin/verifications/${vid}/messages`,
    HELD_MESSAGES: '/admin/messages',
    REPORT_REVIEW: (vid: string) => `/admin/verifications/${vid}/report-review`,
    // TODO(gap): route declared, page not built — PRD "Known Gaps & Roadmap".
    TASK_REVIEW: (taskId: string) => `/admin/tasks/${taskId}/review`,
    CONFIG: '/admin/config',
    TRUST_SCORE_WEIGHTS: '/admin/config/trust-score-weights',
    SYSTEM_CONFIG: '/admin/config/system',
    // TODO(gap): routes declared, pages not built (dispute detail, fraud flags) —
    // PRD "Known Gaps & Roadmap".
    DISPUTE_DETAIL: (id: string) => `/admin/disputes/${id}`,
    FRAUD_FLAGS: '/admin/fraud-flags',
    DISPUTES: '/admin/disputes',
    RECHECKS: '/admin/rechecks',
    PAYOUTS: '/admin/payouts',
    COMMISSION_RULES: '/admin/commission-rules',
    ANALYTICS: '/admin/analytics',
    PRICING: '/admin/pricing',
    FINANCE: '/admin/finance',
    // TODO(gap): finance payments/commissions sub-pages not built — PRD "Known Gaps & Roadmap".
    FINANCE_PAYMENTS: '/admin/finance/payments',
    FINANCE_PAYOUTS: '/admin/finance/payouts',
    FINANCE_COMMISSIONS: '/admin/finance/commissions',
    // TODO(gap): admin content CMS pages not built (pairs with the CONTENT_CREATOR/
    // CONTENT_APPROVER sub-roles) — PRD "Known Gaps & Roadmap".
    CONTENT: '/admin/content',
    CONTENT_HOW_IT_WORKS: '/admin/content/how-it-works',
    CONTENT_FAQS: '/admin/content/faqs',
    CONTENT_TESTIMONIALS: '/admin/content/testimonials',
    CONTENT_AGENT_SPOTLIGHTS: '/admin/content/agent-spotlights',
    CONTENT_AREA_INSIGHTS: '/admin/content/area-insights',
    BROADCASTS: '/admin/broadcasts',
    BROADCAST_NEW: '/admin/broadcasts/new',
    // TODO(gap): route declared, page not built — PRD "Known Gaps & Roadmap".
    BROADCAST_DETAIL: (id: string) => `/admin/broadcasts/${id}`,
    AUDIT_ACTIONS: '/admin/audit/actions',
    VERIFICATION_AUDIT_EXPORT: (vid: string) => `/api/admin/audit/verifications/${vid}/export`,
    ERASURE_REQUESTS: '/admin/erasure-requests',
  },
  PUBLIC: {
    VERIFY: (id: string) => `/verify/${id}`,
    SHARED: (token: string) => `/shared/${token}`,
  },
  PORTAL: {
    GATE: '/portal',
    DASHBOARD: '/portal/dashboard',
    VERIFICATIONS_NEW: '/portal/verifications/new',
    VERIFICATION_DETAIL: (id: string) => `/portal/verifications/${id}`,
    VERIFICATION_CONFIRMED: (id: string) => `/portal/verifications/${id}/confirmed`,
    VERIFICATION_PAY: (id: string) => `/portal/verifications/${id}/pay`,
    VERIFICATION_TRACKING: (id: string) => `/portal/verifications/${id}`,
    VERIFICATION_EVIDENCE: (id: string) => `/portal/verifications/${id}/evidence`,
    VERIFICATION_REPORT: (id: string) => `/portal/verifications/${id}/report`,
    VERIFICATION_MESSAGES: (id: string) => `/portal/verifications/${id}/messages`,
    VERIFICATION_ACTIVITY: (id: string) => `/portal/verifications/${id}/activity`,
    NOTIFICATION_PREFERENCES: '/portal/account/notification-preferences',
    REFERRALS: '/portal/referrals',
    VERIFICATIONS: '/portal/verifications',
    NOTIFICATIONS: '/portal/notifications',
    // TODO(gap): route declared, page not built — PRD "Known Gaps & Roadmap".
    PAYMENTS: '/portal/account/payments',
    SUPPORT: '/portal/support',
    CHAT: '/portal/chat',
  },

  // WhatsApp -> website handoff landings (PRD §7.4.2). Each consumes a signed
  // single-use action token; they are public by design — the token is the authorization,
  // so they must stay outside PROTECTED_PREFIXES in proxy.ts.
  WA: {
    PAY: (token: string) => `/wa/pay/${token}`,
    UPLOAD: (token: string) => `/wa/upload/${token}`,
    REPORT: (token: string) => `/wa/report/${token}`,
  },

  FORBIDDEN: '/forbidden',

  LEGAL: {
    PRIVACY: '/legal/privacy',
    TERMS: '/legal/terms',
    AGENT_TERMS: '/legal/agent-terms',
    VERIFICATION_TERMS: '/legal/verification-terms',
    VERIFICATION_DISCLAIMER: '/legal/verification-disclaimer',
    FINDINGS_OPINION: '/legal/findings-opinion',
    JURISDICTION: '/legal/jurisdiction',
    COMMUNICATION_RECORDING: '/legal/communication-recording',
    REFUND_POLICY: '/legal/refund-policy',
    REPORT_DISCLAIMER: '/legal/report-disclaimer',
  },

  ABOUT: '/about',
  SAMPLE_REPORT: '/sample-report',
  // TODO(gap): legacy PROJECTS/SETTINGS blocks — no pages; remove or build —
  // PRD "Known Gaps & Roadmap".
  PROJECTS: {
    ROOT: '/projects',
    DETAIL: (id: string | number) => `/projects/${id}`,
    NEW: '/projects/new',
  },
  SETTINGS: {
    ACCOUNT: '/settings/account',
    NOTIFICATIONS: '/settings/notifications',
  },
} as const;

/**
 * Paths that sit *inside* a payment flow. Kept beside the route builders they mirror so
 * the two cannot drift: each pattern matches what `PORTAL.VERIFICATION_PAY` / `WA.PAY`
 * produce. The WhatsApp widget suppresses itself here (PRD §7.4.1 — no distraction at
 * the highest-value moment).
 */
export const PAYMENT_FLOW_PATH_PATTERNS: readonly RegExp[] = [
  /^\/portal\/verifications\/[^/]+\/pay\/?$/,
  /^\/wa\/pay(\/|$)/,
] as const;

// export type AuthIntent = 'verify' | 'agent' | 'default';

export const AUTH_INTENTS = [AuthIntent.VERIFY, AuthIntent.AGENT, AuthIntent.DEFAULT, AuthIntent.INVITED_ADMIN] as const satisfies readonly AuthIntent[];

export const isAuthIntent = (value: string | null | undefined): value is AuthIntent =>
  !!value && (AUTH_INTENTS as readonly string[]).includes(value);

export const buildAuthUrl = (
  base: string,
  params: {
    intent?: AuthIntent | null;
    redirect?: string | null;
    tier?: string | null;
    /** Signup prefill (e.g. from an admin-invite preview) — read by SignupContainer. */
    email?: string | null;
    firstName?: string | null;
    lastName?: string | null;
  } = {},
): string => {
  const search = new URLSearchParams();
  if (params.intent && params.intent !== AuthIntent.DEFAULT) search.set('intent', params.intent);
  if (params.redirect) search.set('redirect', params.redirect);
  if (params.tier) search.set('tier', params.tier);
  if (params.email) search.set('email', params.email);
  if (params.firstName) search.set('firstName', params.firstName);
  if (params.lastName) search.set('lastName', params.lastName);
  const qs = search.toString();
  return qs ? `${base}?${qs}` : base;
};

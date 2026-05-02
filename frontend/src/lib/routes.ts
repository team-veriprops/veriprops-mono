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
  },

  ACCOUNT: {
    ROOT: '/account',
    SECURITY: '/account/security',
    DEVICES: '/account/devices',
    LINKED: '/account/linked',
  },

  PORTAL: {
    DASHBOARD: '/portal/dashboard',
    VERIFICATIONS_NEW: '/portal/verifications/new',
    VERIFICATION_DETAIL: (id: string) => `/portal/verifications/${id}`,
    VERIFICATION_CONFIRMED: (id: string) => `/portal/verifications/${id}/confirmed`,
    VERIFICATION_PAY: (id: string) => `/portal/verifications/${id}/pay`,
  },
  AGENT: {
    DASHBOARD: '/agents/dashboard',
    ONBOARDING: '/agents/onboarding',
    ONBOARDING_STATUS: '/agents/onboarding/status',
  },
  ADMIN: {
    DASHBOARD: '/admin/dashboard',
    TEAM: '/admin/team',
    AGENT_APPLICATIONS: '/admin/agents/applications',
    INVITE_ACCEPT: (token: string) => `/auth/admin-invite/${token}`,
  },

  ABOUT: '/about',
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

export type AuthIntent = 'verify' | 'agent' | 'default';

export const AUTH_INTENTS = ['verify', 'agent', 'default'] as const satisfies readonly AuthIntent[];

export const isAuthIntent = (value: string | null | undefined): value is AuthIntent =>
  !!value && (AUTH_INTENTS as readonly string[]).includes(value);

export const buildAuthUrl = (
  base: string,
  params: { intent?: AuthIntent | null; redirect?: string | null; tier?: string | null } = {},
): string => {
  const search = new URLSearchParams();
  if (params.intent && params.intent !== 'default') search.set('intent', params.intent);
  if (params.redirect) search.set('redirect', params.redirect);
  if (params.tier) search.set('tier', params.tier);
  const qs = search.toString();
  return qs ? `${base}?${qs}` : base;
};

export const ROUTES = {
  HOME: '/',

  
  PORTAL: {
    DASHBOARD: '/portal/dashboard',
  },

  ABOUT: '/about',
  LOGIN: '/login',
  SIGNUP: '/signup',
  DASHBOARD: '/dashboard',
  PROJECTS: {
    ROOT: '/projects',
    DETAIL: (id: string | number) => `/projects/${id}`,
    NEW: '/projects/new',
  },
  SETTINGS: {
    ACCOUNT: '/settings/account',
    NOTIFICATIONS: '/settings/notifications',
  },
};

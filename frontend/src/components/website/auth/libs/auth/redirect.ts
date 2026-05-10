import { ROUTES, AuthIntent } from "@/lib/routes";
import { AuthUser, UserType, UserPersona } from "@components/website/auth/models";
/**
 * Post-auth redirect logic. Priority (PRD §2.4):
 *   Admin only           → /admin
 *   Admin + (Agent|...)  → /admin (highest privilege wins)
 *   Agent + Customer     → /agent (toggle to /portal available in header)
 *   Customer only        → /portal
 *
 * If an explicit `intent` was preserved through the auth flow, it can override
 * the default landing — e.g. `intent=verify` lands a Customer on the new-verification
 * wizard rather than the dashboard.
 */
export function resolvePostAuthRedirect(
  user: AuthUser,
  options: { intent?: AuthIntent | null; redirect?: string | null } = {},
): string {
  if (options.redirect && options.redirect.startsWith("/")) {
    return options.redirect;
  }

  if (user.userType === UserType.ADMIN) {
    return ROUTES.ADMIN.DASHBOARD;
  }

  const isAgent = user.personas.includes(UserPersona.AGENT);
  const isCustomer = user.personas.includes(UserPersona.CUSTOMER);

  if (options.intent === "verify" && isCustomer) {
    return ROUTES.PORTAL.VERIFICATIONS_NEW;
  }
  if (options.intent === "agent" && !isAgent) {
    return ROUTES.AGENT.ONBOARDING;
  }

  if (isAgent) return ROUTES.AGENT.DASHBOARD;
  if (isCustomer) return ROUTES.PORTAL.DASHBOARD;

  // No persona yet — default Customer journey.
  return ROUTES.PORTAL.DASHBOARD;
}

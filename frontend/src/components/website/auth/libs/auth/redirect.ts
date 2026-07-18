import { ROUTES} from "@/lib/routes";
import { AuthUser, UserType, UserPersona, AuthIntent } from "@components/website/auth/models";
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
/**
 * True only for a safe same-origin relative path. Rejects protocol-relative
 * (`//evil.com`), backslash (`/\evil.com`), and absolute (`https://…`) URLs so a
 * `?redirect=` param cannot drive a cross-origin navigation (open-redirect phishing).
 */
export function isSafeRedirectPath(value: string | null | undefined): value is string {
  return (
    typeof value === "string" &&
    value.startsWith("/") &&
    !value.startsWith("//") &&
    !value.startsWith("/\\")
  );
}

export function resolvePostAuthRedirect(
  user: AuthUser,
  options: { intent?: AuthIntent | null; redirect?: string | null } = {},
): string {
  if (isSafeRedirectPath(options.redirect)) {
    return options.redirect;
  }

  if (user.userType === UserType.ADMIN) {
    return ROUTES.ADMIN.DASHBOARD;
  }

  const isAgent = user.personas.includes(UserPersona.AGENT);
  const isCustomer = user.personas.includes(UserPersona.CUSTOMER);

  if (options.intent === AuthIntent.AGENT && !isAgent) {
    return ROUTES.AGENT.DASHBOARD;
  }
  // Explicit verify intent, or a customer who has never started a verification
  // (first login after signup, or any later login before their first start) —
  // land straight on the new-verification wizard.
  if (isCustomer && (options.intent === AuthIntent.VERIFY || !user.hasStartedVerification)) {
    return ROUTES.PORTAL.VERIFICATIONS_NEW;
  }

  if (isAgent) return ROUTES.AGENT.DASHBOARD;
  if (isCustomer) return ROUTES.PORTAL.DASHBOARD;

  // No persona yet — default Customer journey.
  return ROUTES.PORTAL.DASHBOARD;
}

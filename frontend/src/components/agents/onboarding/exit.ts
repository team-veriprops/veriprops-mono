import { ROUTES } from "@lib/routes";
import { UserPersona } from "@components/website/auth/models";

/**
 * Where closing the agent application sends someone.
 *
 * Deliberately not `dashboardFor`, which prefers the agent dashboard for anyone holding the agent
 * persona: that is the surface the §3.1 gate covers, so closing the application would put them
 * straight back into the wizard they just closed. Someone with a customer hat has somewhere real
 * to go; someone without one does not, which is what makes the gate compulsory for them.
 */
export function onboardingExitHref(personas: UserPersona[]): string {
  return personas.includes(UserPersona.CUSTOMER)
    ? ROUTES.PORTAL.DASHBOARD
    : ROUTES.AGENT.DASHBOARD;
}

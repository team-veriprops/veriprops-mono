import { describe, it, expect } from "vitest";

import { ROUTES } from "@lib/routes";
import { UserPersona } from "@components/website/auth/models";
import { onboardingExitHref } from "./exit";

describe("onboardingExitHref", () => {
  /**
   * A customer who follows "Become an Agent" and changes their mind must land back where they
   * came from. `dashboardFor` cannot answer this: it prefers the agent dashboard for anyone
   * holding the agent persona, which is where the §3.1 gate would meet them again.
   */
  it("returns a customer to their own portal", () => {
    expect(onboardingExitHref([UserPersona.CUSTOMER])).toBe(ROUTES.PORTAL.DASHBOARD);
    expect(onboardingExitHref([UserPersona.CUSTOMER, UserPersona.AGENT])).toBe(
      ROUTES.PORTAL.DASHBOARD,
    );
  });

  it("sends an agent with no portal back into the agent area", () => {
    // An agent-path signup holds no customer hat, so there is nowhere else for them to be —
    // which is exactly why §3.1's gate is compulsory for them.
    expect(onboardingExitHref([UserPersona.AGENT])).toBe(ROUTES.AGENT.DASHBOARD);
    expect(onboardingExitHref([])).toBe(ROUTES.AGENT.DASHBOARD);
  });
});

import { describe, it, expect } from "vitest";

import { UserPersona } from "@components/website/auth/models";
import type { NavItem } from "./MenuSidebar";
import { visibleNavItems } from "./visibility";

const dashboard: NavItem = { title: "Dashboard", href: "/portal/dashboard", icon: "dashboard" };
const becomeAnAgent: NavItem = {
  title: "Become an Agent",
  href: "/agents/apply",
  icon: "userCog",
  hiddenForAgents: true,
};
const verifyAProperty: NavItem = {
  title: "Verify a Property",
  href: "/agents/verify-property",
  icon: "clipboardList",
  hiddenForCustomers: true,
};

describe("visibleNavItems", () => {
  it("keeps items that address nobody in particular", () => {
    expect(visibleNavItems([dashboard], [])).toEqual([dashboard]);
    expect(visibleNavItems([dashboard], [UserPersona.AGENT, UserPersona.CUSTOMER])).toEqual([
      dashboard,
    ]);
  });

  /**
   * Both entries invite someone to take up a hat they do not hold. Shown to someone who already
   * holds it they are worse than noise — "Become an Agent" points an agent at the application they
   * already made, and `PortalSwitcher` is how they actually cross between portals.
   */
  it("offers a hat only to someone who does not already wear it", () => {
    const items = [dashboard, becomeAnAgent, verifyAProperty];

    expect(visibleNavItems(items, [UserPersona.CUSTOMER])).toEqual([dashboard, becomeAnAgent]);
    expect(visibleNavItems(items, [UserPersona.AGENT])).toEqual([dashboard, verifyAProperty]);
    expect(visibleNavItems(items, [UserPersona.CUSTOMER, UserPersona.AGENT])).toEqual([dashboard]);
  });

  it("shows both invitations to a session that has not loaded yet", () => {
    // A signed-out or still-loading shell holds no personas; hiding an invitation on that basis
    // would make the item flicker away once the session arrives.
    expect(visibleNavItems([becomeAnAgent, verifyAProperty], [])).toEqual([
      becomeAnAgent,
      verifyAProperty,
    ]);
  });

  it("does not mutate the array it was given", () => {
    const items = [dashboard, becomeAnAgent];
    visibleNavItems(items, [UserPersona.AGENT]);
    expect(items).toHaveLength(2);
  });
});

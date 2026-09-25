import { UserPersona } from "@components/website/auth/models";
import type { NavItem } from "./MenuSidebar";

/**
 * Drop the sidebar entries that invite someone to take up a hat they already wear.
 *
 * Both invitations are the same shape in opposite directions — a customer is offered the agent
 * application (§3.1), an agent is offered the customer entry point (§3.2) — so the rule lives here
 * rather than being written twice, and the nav modules stay free of auth concerns.
 */
export function visibleNavItems(navItems: NavItem[], personas: UserPersona[]): NavItem[] {
  const isAgent = personas.includes(UserPersona.AGENT);
  const isCustomer = personas.includes(UserPersona.CUSTOMER);

  return navItems.filter(
    (item) => !(item.hiddenForAgents && isAgent) && !(item.hiddenForCustomers && isCustomer),
  );
}

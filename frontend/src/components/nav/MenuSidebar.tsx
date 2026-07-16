export type NavIconKey =
  | "dashboard"
  | "userCog"
  | "clipboardList"
  | "alertTriangle"
  | "messageSquare"
  | "userRoundKey"
  | "settings"
  | "helpCircle"
  | "fileCheck"
  | "creditCard"
  | "user"
  | "users"
  | "mapPin"
  | "activity"
  | "gift"
  | "bell"
  | "barChart"
  | "tag"
  | "dollarSign"
  | "fileText"
  | "megaphone";

export interface NavItem {
  title: string;
  href: string;
  icon: NavIconKey;
  /** Group label carried by the first item of a sidebar section; following items inherit it. */
  section?: string;
}

export interface NavSection {
  label?: string;
  items: NavItem[];
}

/**
 * Groups a flat nav config into renderable sidebar sections. An item carrying
 * `section` opens a new labeled group; items before the first label form a
 * leading unlabeled group (how the portal/agents menus render as plain lists).
 */
export function groupNavItems(items: NavItem[]): NavSection[] {
  const sections: NavSection[] = [];

  for (const item of items) {
    const startsNewSection = item.section !== undefined || sections.length === 0;
    if (startsNewSection) {
      sections.push({ label: item.section, items: [item] });
    } else {
      sections[sections.length - 1].items.push(item);
    }
  }

  return sections;
}

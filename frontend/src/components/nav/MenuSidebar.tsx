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
  has_separator_after?: boolean;
}

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
  | "mapPin"
  | "activity"
  | "gift";

export interface NavItem {
  title: string;
  href: string;
  icon: NavIconKey;
  has_separator_after?: boolean;
}

export type Crumb = { label: string; href: string; isCurrentPage: boolean };

const STATIC_LABELS: Record<string, string> = {
  // surfaces
  admin: "Admin",
  agents: "Agents",
  portal: "Portal",
  // shared
  dashboard: "Dashboard",
  account: "Account",
  settings: "Settings",
  "notification-preferences": "Notification Preferences",
  notifications: "Notifications",
  messages: "Messages",
  history: "History",
  review: "Review",
  new: "New",
  // admin
  analytics: "Analytics",
  team: "Team",
  verifications: "Verifications",
  applications: "Applications",
  disputes: "Disputes",
  rechecks: "Re-check Requests",
  payouts: "Payouts",
  "commission-rules": "Commission Rules",
  pricing: "Pricing",
  finance: "Finance",
  payments: "Payments",
  commissions: "Commissions",
  content: "Content",
  "how-it-works": "How It Works",
  faqs: "FAQs",
  testimonials: "Testimonials",
  "agent-spotlights": "Agent Spotlights",
  "area-insights": "Area Insights",
  broadcasts: "Broadcasts",
  "fraud-flags": "Fraud Review",
  audit: "Audit",
  actions: "Actions",
  "erasure-requests": "Erasure Requests",
  config: "System Config",
  "trust-score-weights": "Trust Score Weights",
  tasks: "Tasks",
  // agents
  profile: "Profile",
  earnings: "Earnings",
  coverage: "Coverage",
  // portal
  confirmed: "Confirmed",
  pay: "Payment",
  evidence: "Evidence",
  report: "Report",
  activity: "Activity",
  referrals: "Referrals",
  support: "Support",
};

const DYNAMIC_PARENT_LABELS: Record<string, (id: string) => string> = {
  verifications: (id) => `Verification …${id.slice(0, 8)}`,
  broadcasts: (id) => `Broadcast …${id.slice(0, 8)}`,
  tasks: (id) => `Task …${id.slice(0, 8)}`,
};

function isDynamicId(segment: string): boolean {
  return (
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(segment) ||
    /^\d+$/.test(segment) ||
    /^[0-9a-f]{24}$/i.test(segment)
  );
}

function toTitleCase(segment: string): string {
  return segment
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function buildBreadcrumbs(pathname: string): Crumb[] {
  const segments = pathname.split("/").filter(Boolean);
  const crumbs: Crumb[] = [];
  let accumulated = "";

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    accumulated += "/" + seg;
    const isLast = i === segments.length - 1;

    let label: string;
    if (seg in STATIC_LABELS) {
      label = STATIC_LABELS[seg];
    } else if (isDynamicId(seg)) {
      const parentSeg = segments[i - 1];
      const resolver = parentSeg ? DYNAMIC_PARENT_LABELS[parentSeg] : undefined;
      label = resolver ? resolver(seg) : `…${seg.slice(0, 8)}`;
    } else {
      label = toTitleCase(seg);
    }

    crumbs.push({ label, href: accumulated, isCurrentPage: isLast });
  }

  return crumbs;
}

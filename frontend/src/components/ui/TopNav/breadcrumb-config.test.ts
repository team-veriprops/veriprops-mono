import { describe, it, expect } from "vitest";
import { buildBreadcrumbs, type Crumb } from "./breadcrumb-config";

function last(crumbs: Crumb[]): Crumb {
  return crumbs[crumbs.length - 1];
}

describe("buildBreadcrumbs", () => {
  it("returns empty array for empty or root pathname", () => {
    expect(buildBreadcrumbs("")).toEqual([]);
    expect(buildBreadcrumbs("/")).toEqual([]);
  });

  it("returns single crumb for surface root", () => {
    const crumbs = buildBreadcrumbs("/admin");
    expect(crumbs).toHaveLength(1);
    expect(crumbs[0]).toEqual({ label: "Admin", href: "/admin", isCurrentPage: true });
  });

  describe("isCurrentPage flag", () => {
    it("marks only the last crumb as current", () => {
      const crumbs = buildBreadcrumbs("/admin/finance/payments");
      expect(crumbs[0].isCurrentPage).toBe(false);
      expect(crumbs[1].isCurrentPage).toBe(false);
      expect(crumbs[2].isCurrentPage).toBe(true);
    });
  });

  describe("href accumulation", () => {
    it("accumulates path correctly", () => {
      const crumbs = buildBreadcrumbs("/admin/finance/payments");
      expect(crumbs[0].href).toBe("/admin");
      expect(crumbs[1].href).toBe("/admin/finance");
      expect(crumbs[2].href).toBe("/admin/finance/payments");
    });
  });

  describe("admin static routes", () => {
    it("admin/dashboard", () => {
      const crumbs = buildBreadcrumbs("/admin/dashboard");
      expect(crumbs).toHaveLength(2);
      expect(crumbs[0].label).toBe("Admin");
      expect(last(crumbs).label).toBe("Dashboard");
    });

    it("admin/analytics", () => {
      expect(last(buildBreadcrumbs("/admin/analytics")).label).toBe("Analytics");
    });

    it("admin/finance/payments", () => {
      const crumbs = buildBreadcrumbs("/admin/finance/payments");
      expect(crumbs.map((c) => c.label)).toEqual(["Admin", "Finance", "Payments"]);
    });

    it("admin/finance/commissions", () => {
      expect(last(buildBreadcrumbs("/admin/finance/commissions")).label).toBe("Commissions");
    });

    it("admin/content/faqs", () => {
      const crumbs = buildBreadcrumbs("/admin/content/faqs");
      expect(crumbs.map((c) => c.label)).toEqual(["Admin", "Content", "FAQs"]);
    });

    it("admin/content/how-it-works", () => {
      expect(last(buildBreadcrumbs("/admin/content/how-it-works")).label).toBe("How It Works");
    });

    it("admin/content/agent-spotlights", () => {
      expect(last(buildBreadcrumbs("/admin/content/agent-spotlights")).label).toBe("Agent Spotlights");
    });

    it("admin/content/area-insights", () => {
      expect(last(buildBreadcrumbs("/admin/content/area-insights")).label).toBe("Area Insights");
    });

    it("admin/audit/actions", () => {
      const crumbs = buildBreadcrumbs("/admin/audit/actions");
      expect(crumbs.map((c) => c.label)).toEqual(["Admin", "Audit", "Actions"]);
    });

    it("admin/config/trust-score-weights", () => {
      const crumbs = buildBreadcrumbs("/admin/config/trust-score-weights");
      expect(crumbs.map((c) => c.label)).toEqual(["Admin", "System Config", "Trust Score Weights"]);
    });

    it("admin/agents/applications", () => {
      const crumbs = buildBreadcrumbs("/admin/agents/applications");
      expect(crumbs.map((c) => c.label)).toEqual(["Admin", "Agents", "Applications"]);
    });

    it("admin/commission-rules", () => {
      expect(last(buildBreadcrumbs("/admin/commission-rules")).label).toBe("Commission Rules");
    });

    it("admin/fraud-flags", () => {
      expect(last(buildBreadcrumbs("/admin/fraud-flags")).label).toBe("Fraud Review");
    });

    it("admin/erasure-requests", () => {
      expect(last(buildBreadcrumbs("/admin/erasure-requests")).label).toBe("Erasure Requests");
    });

    it("admin/broadcasts/new", () => {
      const crumbs = buildBreadcrumbs("/admin/broadcasts/new");
      expect(crumbs.map((c) => c.label)).toEqual(["Admin", "Broadcasts", "New"]);
    });
  });

  describe("dynamic ID segments", () => {
    const uuid = "abc12345-1234-1234-1234-123456789012";

    it("verification UUID shows contextual label", () => {
      const crumbs = buildBreadcrumbs(`/admin/verifications/${uuid}`);
      expect(last(crumbs).label).toBe("Verification …abc12345");
      expect(last(crumbs).isCurrentPage).toBe(true);
    });

    it("task UUID shows contextual label", () => {
      const crumbs = buildBreadcrumbs(`/admin/tasks/${uuid}/review`);
      expect(crumbs[2].label).toBe("Task …abc12345");
      expect(crumbs[2].isCurrentPage).toBe(false);
      expect(last(crumbs).label).toBe("Review");
    });

    it("broadcast UUID shows contextual label", () => {
      expect(last(buildBreadcrumbs(`/admin/broadcasts/${uuid}`)).label).toBe("Broadcast …abc12345");
    });

    it("portal verification UUID", () => {
      const crumbs = buildBreadcrumbs(`/portal/verifications/${uuid}/messages`);
      expect(crumbs[2].label).toBe("Verification …abc12345");
      expect(last(crumbs).label).toBe("Messages");
    });

    it("agents task UUID with history", () => {
      const crumbs = buildBreadcrumbs(`/agents/tasks/${uuid}/history`);
      expect(crumbs[2].label).toBe("Task …abc12345");
      expect(last(crumbs).label).toBe("History");
    });

    it("unknown parent ID shows truncated form", () => {
      const crumbs = buildBreadcrumbs(`/admin/unknown-domain/${uuid}`);
      expect(last(crumbs).label).toBe(`…${uuid.slice(0, 8)}`);
    });

    it("never exposes full raw UUID", () => {
      const crumbs = buildBreadcrumbs(`/admin/verifications/${uuid}`);
      expect(last(crumbs).label).not.toContain(uuid);
    });
  });

  describe("portal routes", () => {
    it("portal/dashboard", () => {
      expect(last(buildBreadcrumbs("/portal/dashboard")).label).toBe("Dashboard");
    });

    it("portal/verifications/new", () => {
      const crumbs = buildBreadcrumbs("/portal/verifications/new");
      expect(crumbs.map((c) => c.label)).toEqual(["Portal", "Verifications", "New"]);
    });

    it("portal/account/notification-preferences", () => {
      const crumbs = buildBreadcrumbs("/portal/account/notification-preferences");
      expect(crumbs.map((c) => c.label)).toEqual(["Portal", "Account", "Notification Preferences"]);
    });

    it("portal/referrals", () => {
      expect(last(buildBreadcrumbs("/portal/referrals")).label).toBe("Referrals");
    });

    it("portal/support", () => {
      expect(last(buildBreadcrumbs("/portal/support")).label).toBe("Support");
    });
  });

  describe("agents routes", () => {
    it("agents/dashboard", () => {
      const crumbs = buildBreadcrumbs("/agents/dashboard");
      expect(crumbs.map((c) => c.label)).toEqual(["Agents", "Dashboard"]);
    });

    it("agents/settings/coverage", () => {
      const crumbs = buildBreadcrumbs("/agents/settings/coverage");
      expect(crumbs.map((c) => c.label)).toEqual(["Agents", "Settings", "Coverage"]);
    });

    it("agents/account/notification-preferences", () => {
      const crumbs = buildBreadcrumbs("/agents/account/notification-preferences");
      expect(crumbs.map((c) => c.label)).toEqual(["Agents", "Account", "Notification Preferences"]);
    });

    it("agents/earnings", () => {
      expect(last(buildBreadcrumbs("/agents/earnings")).label).toBe("Earnings");
    });
  });

  describe("fallback and edge cases", () => {
    it("unknown segment falls back to title case", () => {
      expect(last(buildBreadcrumbs("/admin/unknown-segment")).label).toBe("Unknown Segment");
    });

    it("buildBreadcrumbs is pure — same input produces identical output", () => {
      const path = "/admin/finance/payments";
      expect(buildBreadcrumbs(path)).toEqual(buildBreadcrumbs(path));
    });
  });
});

import { describe, it, expect } from "vitest";
import { groupNavItems, type NavItem } from "./MenuSidebar";

const item = (title: string, section?: string): NavItem => ({
  title,
  href: `/x/${title.toLowerCase().replace(/\s+/g, "-")}`,
  icon: "dashboard",
  ...(section ? { section } : {}),
});

describe("groupNavItems", () => {
  it("returns a single unlabeled section when no item declares a section", () => {
    const items = [item("Dashboard"), item("My Tasks"), item("Earnings")];
    const sections = groupNavItems(items);

    expect(sections).toHaveLength(1);
    expect(sections[0].label).toBeUndefined();
    expect(sections[0].items.map((i) => i.title)).toEqual(["Dashboard", "My Tasks", "Earnings"]);
  });

  it("starts a new section at each item carrying a section label", () => {
    const items = [
      item("Dashboard", "Overview"),
      item("Analytics"),
      item("Verifications", "Operations"),
      item("Disputes"),
      item("Finance", "Finance"),
    ];
    const sections = groupNavItems(items);

    expect(sections.map((s) => s.label)).toEqual(["Overview", "Operations", "Finance"]);
    expect(sections[0].items.map((i) => i.title)).toEqual(["Dashboard", "Analytics"]);
    expect(sections[1].items.map((i) => i.title)).toEqual(["Verifications", "Disputes"]);
    expect(sections[2].items.map((i) => i.title)).toEqual(["Finance"]);
  });

  it("collects items before the first labeled section into a leading unlabeled section", () => {
    const items = [
      item("Security Activity"),
      item("Password"),
      item("Consents", "Privacy"),
      item("Data & Privacy"),
    ];
    const sections = groupNavItems(items);

    expect(sections).toHaveLength(2);
    expect(sections[0].label).toBeUndefined();
    expect(sections[0].items.map((i) => i.title)).toEqual(["Security Activity", "Password"]);
    expect(sections[1].label).toBe("Privacy");
    expect(sections[1].items.map((i) => i.title)).toEqual(["Consents", "Data & Privacy"]);
  });

  it("returns no sections for an empty list", () => {
    expect(groupNavItems([])).toEqual([]);
  });
});

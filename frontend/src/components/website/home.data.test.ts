import { describe, it, expect } from "vitest";
import {
  pricingTiers,
  methodologySteps,
  ecosystemFeatures,
  agentTypes,
  testimonials,
  navLinks,
  footerLinks,
} from "./home.data";

describe("pricingTiers", () => {
  it("has exactly three tiers", () => {
    expect(pricingTiers).toHaveLength(3);
  });

  it("tiers are ordered Basic, Standard, Premium", () => {
    expect(pricingTiers.map((t) => t.name)).toEqual(["Basic", "Standard", "Premium"]);
  });

  it("each tier has a positive priceNGN and non-empty features", () => {
    for (const tier of pricingTiers) {
      expect(typeof tier.priceNGN).toBe("number");
      expect(tier.priceNGN).toBeGreaterThan(0);
      expect(Array.isArray(tier.features)).toBe(true);
      expect(tier.features.length).toBeGreaterThan(0);
    }
  });

  it("each tier has a cta label and sla string", () => {
    for (const tier of pricingTiers) {
      expect(typeof tier.cta).toBe("string");
      expect(tier.cta.length).toBeGreaterThan(0);
      expect(typeof tier.sla).toBe("string");
      expect(tier.sla.length).toBeGreaterThan(0);
    }
  });

  it("Standard tier is marked popular", () => {
    const standard = pricingTiers.find((t) => t.name === "Standard");
    expect(standard?.popular).toBe(true);
  });

  it("Basic and Premium are not marked popular", () => {
    const basic = pricingTiers.find((t) => t.name === "Basic");
    const premium = pricingTiers.find((t) => t.name === "Premium");
    expect(basic?.popular).toBeFalsy();
    expect(premium?.popular).toBeFalsy();
  });

  it("Premium includes a feature referencing Standard", () => {
    const premium = pricingTiers.find((t) => t.name === "Premium");
    expect(premium?.features.some((f) => f.toLowerCase().includes("standard"))).toBe(true);
  });

  it("Standard includes a feature referencing Basic", () => {
    const standard = pricingTiers.find((t) => t.name === "Standard");
    expect(standard?.features.some((f) => f.toLowerCase().includes("basic"))).toBe(true);
  });
});

describe("methodologySteps", () => {
  it("has exactly 5 steps", () => {
    expect(methodologySteps).toHaveLength(5);
  });

  it("steps are numbered 1 through 5 sequentially", () => {
    methodologySteps.forEach((step, i) => {
      expect(step.step).toBe(i + 1);
    });
  });

  it("each step has a non-empty title and description", () => {
    for (const step of methodologySteps) {
      expect(typeof step.title).toBe("string");
      expect(step.title.length).toBeGreaterThan(2);
      expect(typeof step.description).toBe("string");
      expect(step.description.length).toBeGreaterThan(10);
    }
  });

  it("final step (5) relates to receiving a certified report", () => {
    const last = methodologySteps[4];
    expect(last.title.toLowerCase()).toContain("report");
  });

  it("step 3 relates to encumbrances", () => {
    const step3 = methodologySteps[2];
    expect(step3.title.toLowerCase()).toContain("encumbrance");
  });
});

describe("ecosystemFeatures", () => {
  it("has exactly three features", () => {
    expect(ecosystemFeatures).toHaveLength(3);
  });

  it("includes Trust Score, Verification ID, and Certified Report", () => {
    const titles = ecosystemFeatures.map((f) => f.title);
    expect(titles).toContain("Trust Score");
    expect(titles).toContain("Verification ID");
    expect(titles).toContain("Certified Report");
  });

  it("each feature has a description longer than 20 characters", () => {
    for (const feature of ecosystemFeatures) {
      expect(feature.description.length).toBeGreaterThan(20);
    }
  });

  it("each feature has an icon identifier", () => {
    for (const feature of ecosystemFeatures) {
      expect(typeof feature.icon).toBe("string");
      expect(feature.icon.length).toBeGreaterThan(0);
    }
  });
});

describe("agentTypes", () => {
  it("has exactly four agent types", () => {
    expect(agentTypes).toHaveLength(4);
  });

  it("includes all four required roles", () => {
    const names = agentTypes.map((a) => a.name);
    expect(names).toContain("Field Agent");
    expect(names).toContain("Surveyor");
    expect(names).toContain("Registry Agent");
    expect(names).toContain("Lawyer");
  });

  it("each agent type has a non-empty responsibilities array", () => {
    for (const agent of agentTypes) {
      expect(Array.isArray(agent.responsibilities)).toBe(true);
      expect(agent.responsibilities.length).toBeGreaterThan(0);
    }
  });

  it("each agent type has a description", () => {
    for (const agent of agentTypes) {
      expect(typeof agent.description).toBe("string");
      expect(agent.description.length).toBeGreaterThan(5);
    }
  });
});

describe("testimonials", () => {
  it("has at least three testimonials", () => {
    expect(testimonials.length).toBeGreaterThanOrEqual(3);
  });

  it("each testimonial has name, location, quote, and initials", () => {
    for (const t of testimonials) {
      expect(typeof t.name).toBe("string");
      expect(t.name.length).toBeGreaterThan(0);
      expect(typeof t.location).toBe("string");
      expect(t.location.length).toBeGreaterThan(0);
      expect(typeof t.quote).toBe("string");
      expect(t.quote.length).toBeGreaterThan(30);
      expect(typeof t.initials).toBe("string");
      expect(t.initials.length).toBe(2);
    }
  });

  it("testimonials represent diaspora locations (not Nigeria)", () => {
    const locations = testimonials.map((t) => t.location.toLowerCase());
    const diasporaKeywords = ["uk", "us", "canada", "london", "houston", "toronto", "new york", "manchester"];
    const hasDiaspora = locations.some((loc) =>
      diasporaKeywords.some((kw) => loc.includes(kw))
    );
    expect(hasDiaspora).toBe(true);
  });

  it("testimonials reference different tier levels", () => {
    const tiers = testimonials.map((t) => t.tier);
    const uniqueTiers = new Set(tiers);
    expect(uniqueTiers.size).toBeGreaterThan(1);
  });
});

describe("navLinks", () => {
  it("includes a pricing link", () => {
    const hrefs = navLinks.map((l) => l.href);
    expect(hrefs).toContain("#pricing");
  });

  it("includes a how-it-works link", () => {
    const hrefs = navLinks.map((l) => l.href);
    expect(hrefs).toContain("#how-it-works");
  });

  it("each nav link has a label", () => {
    for (const link of navLinks) {
      expect(typeof link.label).toBe("string");
      expect(link.label.length).toBeGreaterThan(0);
    }
  });
});

describe("footerLinks", () => {
  it("has resources, company, and socials groups", () => {
    expect(Array.isArray(footerLinks.resources)).toBe(true);
    expect(Array.isArray(footerLinks.company)).toBe(true);
    expect(Array.isArray(footerLinks.socials)).toBe(true);
  });

  it("resources has at least 3 links", () => {
    expect(footerLinks.resources.length).toBeGreaterThanOrEqual(3);
  });

  it("company has Privacy Policy and Terms of Service", () => {
    const labels = footerLinks.company.map((l) => l.label);
    expect(labels).toContain("Privacy Policy");
    expect(labels).toContain("Terms of Service");
  });
});

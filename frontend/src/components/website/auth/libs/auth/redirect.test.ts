import { describe, it, expect } from "vitest";
import { resolvePostAuthRedirect } from "./redirect";
import { TransactionCurrency } from "@/types/models";
import { AuthUser, TrustStatus, UserPersona, UserType } from "@components/website/auth/models";
const baseUser: AuthUser = {
  id: "u_1",
  firstName: "Ada",
  lastName: "W",
  email: "ada@example.com",
  emailVerified: true,
  phone: "8012345678",
  phoneCountryCode: "NG",
  phoneDialCode: "+234",
  phoneVerified: true,
  countryOfResidence: "NG",
  timezone: "Africa/Lagos",
  preferredCurrency: TransactionCurrency.NGN,
  userType: UserType.USER,
  personas: [UserPersona.CUSTOMER],
  trustStatus: TrustStatus.UNTRUSTED,
  hasPassword: true,
  linkedProviders: [],
  createdAt: new Date().toISOString(),
};

describe("resolvePostAuthRedirect", () => {
  it("admin always lands on /admin/dashboard", () => {
    const dest = resolvePostAuthRedirect({
      ...baseUser,
      userType: UserType.ADMIN,
      personas: [],
    });
    expect(dest).toBe("/admin/dashboard");
  });

  it("admin + agent + customer still lands on /admin (highest privilege wins)", () => {
    const dest = resolvePostAuthRedirect({
      ...baseUser,
      userType: UserType.ADMIN,
      personas: [UserPersona.AGENT, UserPersona.CUSTOMER],
    });
    expect(dest).toBe("/admin/dashboard");
  });

  it("agent + customer lands on /agents/dashboard (default toggle)", () => {
    const dest = resolvePostAuthRedirect({
      ...baseUser,
      personas: [UserPersona.AGENT, UserPersona.CUSTOMER],
    });
    expect(dest).toBe("/agents/dashboard");
  });

  it("customer only lands on /portal", () => {
    const dest = resolvePostAuthRedirect(baseUser);
    expect(dest).toBe("/portal/dashboard");
  });

  it("intent=verify routes a customer to verifications/new", () => {
    const dest = resolvePostAuthRedirect(baseUser, { intent: "verify" });
    expect(dest).toBe("/portal/verifications/new");
  });

  it("intent=agent for non-agent customer routes to onboarding", () => {
    const dest = resolvePostAuthRedirect(baseUser, { intent: "agent" });
    expect(dest).toBe("/agents/onboarding");
  });

  it("explicit redirect param overrides defaults", () => {
    const dest = resolvePostAuthRedirect(baseUser, { redirect: "/portal/verifications/abc" });
    expect(dest).toBe("/portal/verifications/abc");
  });

  it("ignores unsafe absolute redirect URLs", () => {
    const dest = resolvePostAuthRedirect(baseUser, {
      redirect: "https://attacker.example.com/take-over",
    });
    expect(dest).toBe("/portal/dashboard");
  });
});

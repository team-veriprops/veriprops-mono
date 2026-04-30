import { describe, it, expect } from "vitest";
import {
  signupStep1Schema,
  signupStep2Schema,
  signupStep3Schema,
  signupStep4Schema,
  loginSchema,
  forgotPasswordSchema,
  resetPasswordSchema,
  RATE_LIMIT_LOCKOUT_AT,
  RATE_LIMIT_WARN_AT,
} from "./schemas";
import { TransactionCurrency } from "@/types/models";

describe("signupStep1Schema", () => {
  const valid = {
    firstName: "Adaeze",
    lastName: "Williams",
    email: "ada@example.com",
    password: "Sup3rSecure!Pwd",
  };

  it("accepts a well-formed payload", () => {
    expect(signupStep1Schema.parse(valid)).toMatchObject(valid);
  });

  it("rejects empty first name", () => {
    expect(() => signupStep1Schema.parse({ ...valid, firstName: "" })).toThrow();
  });

  it("rejects malformed email", () => {
    expect(() => signupStep1Schema.parse({ ...valid, email: "not-an-email" })).toThrow();
  });

  it("rejects passwords shorter than 8 characters", () => {
    expect(() => signupStep1Schema.parse({ ...valid, password: "Ab1!" })).toThrow();
  });

  it("rejects passwords with no uppercase", () => {
    expect(() => signupStep1Schema.parse({ ...valid, password: "alllower1!" })).toThrow();
  });

  it("rejects passwords with no number", () => {
    expect(() => signupStep1Schema.parse({ ...valid, password: "AllLetters!" })).toThrow();
  });
});

describe("signupStep2Schema", () => {
  const valid = {
    countryCode: "NG",
    dialCode: "+234",
    phone: "8012345678",
    emailVerified: true as const,
    phoneVerified: true as const,
  };

  it("accepts a verified payload", () => {
    expect(signupStep2Schema.parse(valid)).toMatchObject(valid);
  });

  it("requires emailVerified=true", () => {
    expect(() => signupStep2Schema.parse({ ...valid, emailVerified: false })).toThrow();
  });

  it("requires phoneVerified=true", () => {
    expect(() => signupStep2Schema.parse({ ...valid, phoneVerified: false })).toThrow();
  });

  it("rejects non-numeric phone", () => {
    expect(() => signupStep2Schema.parse({ ...valid, phone: "12-34" })).toThrow();
  });

  it("rejects too-short phone", () => {
    expect(() => signupStep2Schema.parse({ ...valid, phone: "123" })).toThrow();
  });
});

describe("signupStep3Schema", () => {
  it("accepts a complete residence payload", () => {
    const result = signupStep3Schema.parse({
      countryOfResidence: "NG",
      timezone: "Africa/Lagos",
      preferredCurrency: TransactionCurrency.NGN,
    });
    expect(result.preferredCurrency).toBe(TransactionCurrency.NGN);
  });

  it("rejects empty country", () => {
    expect(() =>
      signupStep3Schema.parse({
        countryOfResidence: "",
        timezone: "Africa/Lagos",
        preferredCurrency: TransactionCurrency.NGN,
      }),
    ).toThrow();
  });

  it("rejects unsupported currency", () => {
    expect(() =>
      signupStep3Schema.parse({
        countryOfResidence: "NG",
        timezone: "Africa/Lagos",
        preferredCurrency: "BTC" as TransactionCurrency,
      }),
    ).toThrow();
  });
});

describe("signupStep4Schema", () => {
  it("accepts both consents", () => {
    expect(
      signupStep4Schema.parse({
        acceptedPlatformTerms: true,
        acceptedPrivacyPolicy: true,
      }),
    ).toBeTruthy();
  });

  it("rejects when terms not accepted", () => {
    expect(() =>
      signupStep4Schema.parse({
        acceptedPlatformTerms: false,
        acceptedPrivacyPolicy: true,
      }),
    ).toThrow();
  });
});

describe("loginSchema", () => {
  it("accepts a basic email + password", () => {
    expect(
      loginSchema.parse({ email: "ada@example.com", password: "any-non-empty" }),
    ).toMatchObject({ email: "ada@example.com" });
  });

  it("rejects empty password", () => {
    expect(() =>
      loginSchema.parse({ email: "ada@example.com", password: "" }),
    ).toThrow();
  });
});

describe("forgotPasswordSchema", () => {
  it("rejects malformed email", () => {
    expect(() => forgotPasswordSchema.parse({ email: "no" })).toThrow();
  });
});

describe("resetPasswordSchema", () => {
  it("requires matching confirmation", () => {
    expect(() =>
      resetPasswordSchema.parse({
        password: "Sup3rSecure!",
        confirmPassword: "different-Sup3r!",
      }),
    ).toThrow();
  });

  it("accepts matching confirmation", () => {
    expect(
      resetPasswordSchema.parse({
        password: "Sup3rSecure!",
        confirmPassword: "Sup3rSecure!",
      }),
    ).toMatchObject({ password: "Sup3rSecure!" });
  });
});

describe("rate-limit constants", () => {
  it("warns before lockout", () => {
    expect(RATE_LIMIT_WARN_AT).toBeLessThan(RATE_LIMIT_LOCKOUT_AT);
  });
});

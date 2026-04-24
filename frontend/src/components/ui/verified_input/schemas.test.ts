import { describe, it, expect } from "vitest";
import { verifyFormSchema } from "./schemas";

describe("verifyFormSchema", () => {
  const valid = {
    email: "user@example.com",
    countryCode: "NG",
    dialCode: "+234",
    phone: "8012345678",
    emailVerified: true,
    phoneVerified: true,
  };

  it("should pass when all fields are valid and both verified flags are true", () => {
    expect(verifyFormSchema.safeParse(valid).success).toBe(true);
  });

  it("should fail when email is not a valid email address", () => {
    const result = verifyFormSchema.safeParse({ ...valid, email: "bad-email" });
    expect(result.success).toBe(false);
    const issue = result.error?.issues.find((i) => i.path[0] === "email");
    expect(issue?.message).toBe("Please enter a valid email address");
  });

  it("should fail when countryCode is empty", () => {
    const result = verifyFormSchema.safeParse({ ...valid, countryCode: "" });
    expect(result.success).toBe(false);
    const issue = result.error?.issues.find((i) => i.path[0] === "countryCode");
    expect(issue?.message).toBe("Country code is required");
  });

  it("should fail when dialCode is empty", () => {
    const result = verifyFormSchema.safeParse({ ...valid, dialCode: "" });
    expect(result.success).toBe(false);
    const issue = result.error?.issues.find((i) => i.path[0] === "dialCode");
    expect(issue?.message).toBe("Dial code is required");
  });

  it("should fail when phone contains non-digit characters", () => {
    const result = verifyFormSchema.safeParse({ ...valid, phone: "080-123-456" });
    expect(result.success).toBe(false);
    const issue = result.error?.issues.find((i) => i.path[0] === "phone");
    expect(issue?.message).toBe("Phone must contain only digits");
  });

  it("should fail when phone is shorter than 7 digits", () => {
    const result = verifyFormSchema.safeParse({ ...valid, phone: "123456" });
    expect(result.success).toBe(false);
  });

  it("should fail when phone is longer than 15 digits", () => {
    const result = verifyFormSchema.safeParse({ ...valid, phone: "1234567890123456" });
    expect(result.success).toBe(false);
  });

  it("should fail when emailVerified is false", () => {
    const result = verifyFormSchema.safeParse({ ...valid, emailVerified: false });
    expect(result.success).toBe(false);
    const issue = result.error?.issues.find((i) => i.path[0] === "emailVerified");
    expect(issue?.message).toBe("Email must be verified");
  });

  it("should fail when phoneVerified is false", () => {
    const result = verifyFormSchema.safeParse({ ...valid, phoneVerified: false });
    expect(result.success).toBe(false);
    const issue = result.error?.issues.find((i) => i.path[0] === "phoneVerified");
    expect(issue?.message).toBe("Phone must be verified");
  });

  it("should fail when both emailVerified and phoneVerified are false", () => {
    const result = verifyFormSchema.safeParse({
      ...valid,
      emailVerified: false,
      phoneVerified: false,
    });
    expect(result.success).toBe(false);
    expect(result.error?.issues).toHaveLength(2);
  });
});

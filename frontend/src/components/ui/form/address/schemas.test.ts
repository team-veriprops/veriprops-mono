import { describe, it, expect } from "vitest";
import { addressSchema } from "./schemas";

describe("addressSchema", () => {
  const valid = {
    address: "123 Broad Street, Lagos Island",
    country: "Nigeria",
    state: "Lagos",
    latitude: "6.4541",
    longitude: "3.3947",
    placeId: "ChIJxxxxxxxx",
  };

  it("should pass when all required fields are valid and country is Nigeria", () => {
    expect(addressSchema.safeParse(valid).success).toBe(true);
  });

  it("should pass when optional fields are omitted", () => {
    expect(addressSchema.safeParse(valid).success).toBe(true);
  });

  it("should pass when optional fields are provided", () => {
    expect(
      addressSchema.safeParse({
        ...valid,
        lga: "Lagos Island",
        city: "Lagos",
        area: "CMS",
        street: "Broad Street",
        streetNumber: "123",
        postalCode: "100001",
      }).success
    ).toBe(true);
  });

  it("should fail when address is shorter than 5 characters", () => {
    const result = addressSchema.safeParse({ ...valid, address: "Abc" });
    expect(result.success).toBe(false);
    const issue = result.error?.issues.find((i) => i.path[0] === "address");
    expect(issue?.message).toBe("Select a valid address");
  });

  it("should fail when state is shorter than 2 characters", () => {
    const result = addressSchema.safeParse({ ...valid, state: "L" });
    expect(result.success).toBe(false);
    const issue = result.error?.issues.find((i) => i.path[0] === "state");
    expect(issue?.message).toBe("State is required");
  });

  it("should fail when latitude is empty", () => {
    const result = addressSchema.safeParse({ ...valid, latitude: "" });
    expect(result.success).toBe(false);
    const issue = result.error?.issues.find((i) => i.path[0] === "latitude");
    expect(issue?.message).toBe("Latitude missing");
  });

  it("should fail when longitude is empty", () => {
    const result = addressSchema.safeParse({ ...valid, longitude: "" });
    expect(result.success).toBe(false);
    const issue = result.error?.issues.find((i) => i.path[0] === "longitude");
    expect(issue?.message).toBe("Longitude missing");
  });

  it("should fail when placeId is empty", () => {
    const result = addressSchema.safeParse({ ...valid, placeId: "" });
    expect(result.success).toBe(false);
    const issue = result.error?.issues.find((i) => i.path[0] === "placeId");
    expect(issue?.message).toBe("Select an address from suggestions");
  });

  it("should fail when country is not Nigeria", () => {
    const result = addressSchema.safeParse({ ...valid, country: "Ghana" });
    expect(result.success).toBe(false);
    const issue = result.error?.issues.find((i) => i.path[0] === "country");
    expect(issue?.message).toBe("Address must be in Nigeria");
  });
});

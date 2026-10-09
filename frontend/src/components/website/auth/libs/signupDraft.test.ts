import { describe, it, expect, beforeEach } from "vitest";
import {
  saveLocalDraft,
  loadLocalDraft,
  loadActiveLocalDraft,
  clearLocalDraft,
  type SignupDraftFields,
} from "./signupDraft";

const FIELDS: SignupDraftFields = {
  email: "test@example.com",
  firstName: "Ada",
  lastName: "Obi",
  countryCode: "NG",
  dialCode: "+234",
  phone: "8012345678",
};

const storedValues = () =>
  Array.from({ length: localStorage.length }, (_, i) => localStorage.getItem(localStorage.key(i)!) ?? "");

beforeEach(() => {
  localStorage.clear();
});

describe("saveLocalDraft + loadLocalDraft", () => {
  it("round-trips the draft's fields", () => {
    saveLocalDraft("test@example.com", FIELDS);
    expect(loadLocalDraft("test@example.com")?.fields).toEqual(FIELDS);
  });

  it("is case-insensitive for email lookup", () => {
    saveLocalDraft("Ada@example.com", FIELDS);
    expect(loadLocalDraft("ADA@EXAMPLE.COM")?.fields.firstName).toBe("Ada");
  });

  it("returns null for an unknown email", () => {
    expect(loadLocalDraft("nobody@example.com")).toBeNull();
  });

  it("overwrites when saved twice", () => {
    saveLocalDraft("test@example.com", { ...FIELDS, firstName: "First" });
    saveLocalDraft("test@example.com", { ...FIELDS, firstName: "Second" });
    expect(loadLocalDraft("test@example.com")?.fields.firstName).toBe("Second");
  });
});

describe("what never reaches storage", () => {
  it("drops the password and the verified flags on save", () => {
    saveLocalDraft("test@example.com", {
      ...FIELDS,
      password: "Secret1234!",
      emailVerified: true,
      phoneVerified: true,
    } as SignupDraftFields);

    const stored = storedValues().join("\n");
    expect(stored).not.toContain("Secret1234!");
    expect(stored).not.toContain("password");
    expect(stored).not.toContain("Verified");
    expect(loadLocalDraft("test@example.com")?.fields).toEqual(FIELDS);
  });

  it("purges the password from a legacy draft when it is read", () => {
    localStorage.setItem(
      "veriprops-signup-draft:legacy@example.com",
      JSON.stringify({
        email: "legacy@example.com",
        step: 2,
        payload: { email: "legacy@example.com", firstName: "Ada", password: "Secret1234!", emailVerified: true },
        dateUpdated: "2026-01-01T00:00:00.000Z",
      }),
    );
    localStorage.setItem("veriprops-signup-draft:active-email", "legacy@example.com");

    const draft = loadActiveLocalDraft();

    expect(draft?.fields).toEqual({ email: "legacy@example.com", firstName: "Ada" });
    expect(storedValues().join("\n")).not.toContain("Secret1234!");
  });

  it("purges a legacy draft that is not the active one too", () => {
    localStorage.setItem(
      "veriprops-signup-draft:other@example.com",
      JSON.stringify({ email: "other@example.com", payload: { password: "Secret1234!" } }),
    );

    loadActiveLocalDraft();

    expect(storedValues().join("\n")).not.toContain("Secret1234!");
  });
});

describe("loadActiveLocalDraft", () => {
  it("returns null when nothing has been saved", () => {
    expect(loadActiveLocalDraft()).toBeNull();
  });

  it("returns the most-recently saved draft", () => {
    saveLocalDraft("a@example.com", { email: "a@example.com" });
    saveLocalDraft("b@example.com", { email: "b@example.com" });
    expect(loadActiveLocalDraft()?.email).toBe("b@example.com");
  });
});

describe("clearLocalDraft", () => {
  it("removes the draft and clears the active pointer", () => {
    saveLocalDraft("test@example.com", FIELDS);
    clearLocalDraft("test@example.com");
    expect(loadLocalDraft("test@example.com")).toBeNull();
    expect(loadActiveLocalDraft()).toBeNull();
  });

  it("does not clear a different email's draft", () => {
    saveLocalDraft("a@example.com", { email: "a@example.com" });
    saveLocalDraft("b@example.com", { email: "b@example.com" });
    clearLocalDraft("a@example.com");
    expect(loadLocalDraft("b@example.com")?.email).toBe("b@example.com");
  });
});

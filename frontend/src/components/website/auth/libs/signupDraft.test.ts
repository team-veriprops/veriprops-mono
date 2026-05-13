import { describe, it, expect, beforeEach } from "vitest";
import {
  saveLocalDraft,
  loadLocalDraft,
  loadActiveLocalDraft,
  clearLocalDraft,
} from "./signupDraft";
import type { SignupDraft } from "../models";

function makeDraft(overrides?: Partial<SignupDraft>): SignupDraft {
  return {
    email: "test@example.com",
    step: 1,
    payload: { email: "test@example.com", firstName: "Ada", lastName: "Obi" },
    dateUpdated: "2026-01-01T00:00:00.000Z",
    ...overrides,
  };
}

beforeEach(() => {
  localStorage.clear();
});

describe("saveLocalDraft + loadLocalDraft", () => {
  it("round-trips a draft", () => {
    const draft = makeDraft();
    saveLocalDraft(draft);
    expect(loadLocalDraft(draft.email)).toEqual(draft);
  });

  it("is case-insensitive for email lookup", () => {
    const draft = makeDraft({ email: "Ada@example.com" });
    saveLocalDraft(draft);
    expect(loadLocalDraft("ADA@EXAMPLE.COM")).toEqual(draft);
  });

  it("returns null for an unknown email", () => {
    expect(loadLocalDraft("nobody@example.com")).toBeNull();
  });

  it("overwrites when saved twice", () => {
    const first = makeDraft({ step: 1 });
    const second = makeDraft({ step: 2 });
    saveLocalDraft(first);
    saveLocalDraft(second);
    expect(loadLocalDraft("test@example.com")?.step).toBe(2);
  });
});

describe("loadActiveLocalDraft", () => {
  it("returns null when nothing has been saved", () => {
    expect(loadActiveLocalDraft()).toBeNull();
  });

  it("returns the most-recently saved draft", () => {
    const draft = makeDraft({ step: 2 });
    saveLocalDraft(draft);
    expect(loadActiveLocalDraft()?.step).toBe(2);
  });
});

describe("clearLocalDraft", () => {
  it("removes the draft and clears the active pointer", () => {
    const draft = makeDraft();
    saveLocalDraft(draft);
    clearLocalDraft(draft.email);
    expect(loadLocalDraft(draft.email)).toBeNull();
    expect(loadActiveLocalDraft()).toBeNull();
  });

  it("does not clear a different email's draft", () => {
    const a = makeDraft({ email: "a@example.com", payload: { email: "a@example.com" } });
    const b = makeDraft({ email: "b@example.com", payload: { email: "b@example.com" } });
    saveLocalDraft(a);
    saveLocalDraft(b);
    clearLocalDraft("a@example.com");
    expect(loadLocalDraft("b@example.com")).toEqual(b);
  });
});

import { describe, expect, it } from "vitest";
import { majorToMinor, minorToMajorText } from "@lib/utils";

/** Admins type money in naira; the backend stores kobo. These two convert at the input. */
describe("majorToMinor", () => {
  it.each([
    ["5000", 500_000],
    ["5,000.50", 500_050],
    ["0", 0],
  ])("reads %s as %i kobo", (text, minor) => {
    expect(majorToMinor(text)).toBe(minor);
  });

  it.each(["", "abc", "-1", "1.234"])("refuses %s", (text) => {
    expect(majorToMinor(text)).toBeUndefined();
  });
});

describe("minorToMajorText", () => {
  it.each([
    [500_000, "5000"],
    [500_050, "5000.5"],
    [0, "0"],
    [null, "0"],
  ])("prefills %s kobo as %s", (minor, text) => {
    expect(minorToMajorText(minor)).toBe(text);
  });

  it("round-trips through majorToMinor", () => {
    expect(majorToMinor(minorToMajorText(1_234_567))).toBe(1_234_567);
  });
});

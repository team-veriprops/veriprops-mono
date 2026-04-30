import { describe, it, expect } from "vitest";
import { scorePassword } from "./password-strength";

describe("scorePassword", () => {
  it("scores empty as 0", () => {
    expect(scorePassword("").score).toBe(0);
  });

  it("scores common passwords as 0", () => {
    expect(scorePassword("password").score).toBe(0);
    expect(scorePassword("123456").score).toBe(0);
  });

  it("scores short passwords low", () => {
    expect(scorePassword("Ab1!").score).toBeLessThanOrEqual(1);
  });

  it("scores diverse, long passwords high", () => {
    expect(scorePassword("Sup3rSecure!Pwd").score).toBeGreaterThanOrEqual(3);
  });

  it("penalises repeating characters", () => {
    const repeating = scorePassword("Aaaa1234!!!");
    const distinct  = scorePassword("Bv4n#tEarly!");
    expect(distinct.score).toBeGreaterThanOrEqual(repeating.score);
  });

  it("penalises sequential digits", () => {
    const seq = scorePassword("Abcd1234!");
    expect(seq.score).toBeLessThanOrEqual(3);
  });
});

import { describe, expect, it } from "vitest";
import { fitWithin, jpegDataUrl } from "./image";

describe("fitWithin", () => {
  it("scales the longer edge down to the limit, keeping proportions", () => {
    expect(fitWithin(4000, 3000, 1280)).toEqual({ width: 1280, height: 960 });
    expect(fitWithin(3000, 4000, 1280)).toEqual({ width: 960, height: 1280 });
  });

  it("never enlarges a photo that is already small enough", () => {
    expect(fitWithin(640, 480, 1280)).toEqual({ width: 640, height: 480 });
  });

  it("never draws a zero-sized image", () => {
    expect(fitWithin(10_000, 1, 1280)).toEqual({ width: 1280, height: 1 });
  });
});

describe("jpegDataUrl", () => {
  it("shows base64 JPEG as an image source", () => {
    expect(jpegDataUrl("/9j/abc")).toBe("data:image/jpeg;base64,/9j/abc");
  });
});

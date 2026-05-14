import { describe, it, expect, vi, beforeEach } from "vitest";
import { PublicVerificationService } from "./public-verification-service";
import type { HttpClient } from "@lib/FetchHttpClient";
import type { PublicVerificationSummary } from "../models";

const mockSummary: PublicVerificationSummary = {
  vid: "VP-2026-PUB001",
  tier: "STANDARD",
  propertyType: "RESIDENTIAL",
  state: "LAGOS",
  lga: "Eti-Osa",
  status: "COMPLETED",
  trustBand: "HIGH",
  reportDate: "2026-05-14T00:00:00Z",
  sharingMode: "PUBLIC",
};

function makeHttp(): { mock: Record<string, ReturnType<typeof vi.fn>>; client: HttpClient } {
  const mock = {
    get: vi.fn(),
    getBlob: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  };
  return { mock, client: mock as unknown as HttpClient };
}

describe("PublicVerificationService", () => {
  let http: ReturnType<typeof makeHttp>;
  let service: PublicVerificationService;

  beforeEach(() => {
    http = makeHttp();
    service = new PublicVerificationService(http.client);
  });

  describe("getSummary", () => {
    it("calls GET /public/verifications/{vid} with cache: no-store", async () => {
      http.mock.get.mockResolvedValue({ data: mockSummary });

      await service.getSummary("VP-2026-PUB001");

      expect(http.mock.get).toHaveBeenCalledWith(
        "/public/verifications/VP-2026-PUB001",
        { cache: "no-store" },
      );
    });

    it("returns the summary from the response data field", async () => {
      http.mock.get.mockResolvedValue({ data: mockSummary });

      const result = await service.getSummary("VP-2026-PUB001");

      expect(result).toEqual(mockSummary);
    });

    it("returns null when the http client throws", async () => {
      http.mock.get.mockRejectedValue(new Error("Not found"));

      const result = await service.getSummary("VP-2026-MISSING");

      expect(result).toBeNull();
    });

    it("returns null when response has no data field", async () => {
      http.mock.get.mockResolvedValue({});

      const result = await service.getSummary("VP-2026-PUB001");

      expect(result).toBeNull();
    });

    it("returns null when response data is null", async () => {
      http.mock.get.mockResolvedValue({ data: null });

      const result = await service.getSummary("VP-2026-PUB001");

      expect(result).toBeNull();
    });
  });
});

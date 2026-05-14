import { describe, it, expect, vi, beforeEach } from "vitest";
import { ReportService } from "./report-service";
import type { HttpClient } from "@lib/FetchHttpClient";

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

describe("ReportService", () => {
  let http: ReturnType<typeof makeHttp>;
  let service: ReportService;

  beforeEach(() => {
    http = makeHttp();
    service = new ReportService(http.client);
  });

  describe("acknowledge", () => {
    it("posts to /portal/verifications/{vid}/report/acknowledge with ip_address null", async () => {
      http.mock.post.mockResolvedValue(undefined);

      await service.acknowledge("VP-2026-001");

      expect(http.mock.post).toHaveBeenCalledWith(
        "/portal/verifications/VP-2026-001/report/acknowledge",
        { ip_address: null },
      );
    });

    it("calls post once per invocation", async () => {
      http.mock.post.mockResolvedValue(undefined);

      await service.acknowledge("VP-2026-001");

      expect(http.mock.post).toHaveBeenCalledTimes(1);
    });

    it("propagates errors from the http client", async () => {
      const error = new Error("Network error");
      http.mock.post.mockRejectedValue(error);

      await expect(service.acknowledge("VP-2026-001")).rejects.toThrow("Network error");
    });
  });

  describe("downloadPdf", () => {
    it("calls getBlob on /portal/verifications/{id}/report/pdf", async () => {
      const fakeBlob = new Blob(["pdf"], { type: "application/pdf" });
      http.mock.getBlob.mockResolvedValue(fakeBlob);

      const result = await service.downloadPdf("VP-2026-001");

      expect(http.mock.getBlob).toHaveBeenCalledWith(
        "/portal/verifications/VP-2026-001/report/pdf",
      );
      expect(result).toBe(fakeBlob);
    });

    it("returns the blob from the http client", async () => {
      const fakeBlob = new Blob(["content"], { type: "application/pdf" });
      http.mock.getBlob.mockResolvedValue(fakeBlob);

      const result = await service.downloadPdf("abc-123");

      expect(result).toBeInstanceOf(Blob);
    });

    it("propagates errors from the http client", async () => {
      http.mock.getBlob.mockRejectedValue(new Error("PDF unavailable"));

      await expect(service.downloadPdf("VP-2026-001")).rejects.toThrow("PDF unavailable");
    });
  });
});

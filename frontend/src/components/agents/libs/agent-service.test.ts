import { describe, it, expect, vi, beforeEach } from "vitest";
import { AgentService } from "./agent-service";
import type { HttpClient } from "@lib/FetchHttpClient";
import type { AgentApplication, BvnVerificationResult } from "./agent-service";

const mockApp: AgentApplication = {
  id: "app_1",
  userId: "u_1",
  status: "DRAFT",
  types: [],
  kycMethod: null,
  bvnLast4: null,
  bvnVerifiedAt: null,
  idDocType: null,
  idDocUploaded: false,
  selfieUploaded: false,
  selfieMatchScore: null,
  surveyorLicenceNo: null,
  nbaLicenceNo: null,
  yearsOfExperience: null,
  coverageStates: [],
  coverageLgas: [],
  bio: null,
  submittedAt: null,
  reviewedAt: null,
  rejectionReason: null,
  createdAt: "2026-05-07T00:00:00Z",
  updatedAt: null,
};

function makeHttp(): { mock: Record<string, ReturnType<typeof vi.fn>>; client: HttpClient } {
  const mock = {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  };
  return { mock, client: mock as unknown as HttpClient };
}

describe("AgentService", () => {
  let http: ReturnType<typeof makeHttp>;
  let service: AgentService;

  beforeEach(() => {
    http = makeHttp();
    service = new AgentService(http.client);
  });

  it("getMyApplication calls GET /users/agents/me/application", async () => {
    http.mock.get.mockResolvedValue({ data: mockApp });
    const result = await service.getMyApplication();
    expect(http.mock.get).toHaveBeenCalledWith("/users/agents/me/application");
    expect(result.data).toEqual(mockApp);
  });

  it("saveTypesStep calls POST /users/agents/me/application/types with payload", async () => {
    const updated = { ...mockApp, types: ["FIELD"] as AgentApplication["types"] };
    http.mock.post.mockResolvedValue({ data: updated });
    const result = await service.saveTypesStep({ types: ["FIELD"] });
    expect(http.mock.post).toHaveBeenCalledWith(
      "/users/agents/me/application/types",
      { types: ["FIELD"] },
    );
    expect(result.data?.types).toEqual(["FIELD"]);
  });

  it("verifyBvn calls POST /users/agents/me/application/kyc/bvn", async () => {
    const bvnResult: BvnVerificationResult = {
      verified: true,
      bvnLast4: "4567",
      verificationId: "vrf_abc",
      failureReason: null,
    };
    http.mock.post.mockResolvedValue({ data: bvnResult });
    const result = await service.verifyBvn({ bvn: "12345678901" });
    expect(http.mock.post).toHaveBeenCalledWith(
      "/users/agents/me/application/kyc/bvn",
      { bvn: "12345678901" },
    );
    expect(result.data?.verified).toBe(true);
    expect(result.data?.bvnLast4).toBe("4567");
  });

  it("uploadKycDocs calls POST /users/agents/me/application/kyc/documents", async () => {
    http.mock.post.mockResolvedValue({ data: mockApp });
    await service.uploadKycDocs({
      idDocType: "PASSPORT",
      idDocUrl: "https://s3.example.com/id.jpg",
      selfieUrl: "https://s3.example.com/selfie.jpg",
    });
    expect(http.mock.post).toHaveBeenCalledWith(
      "/users/agents/me/application/kyc/documents",
      expect.objectContaining({ idDocType: "PASSPORT" }),
    );
  });

  it("saveCredentialsStep calls POST /users/agents/me/application/credentials", async () => {
    http.mock.post.mockResolvedValue({ data: mockApp });
    await service.saveCredentialsStep({ coverageStates: ["LAGOS"], coverageLgas: [] });
    expect(http.mock.post).toHaveBeenCalledWith(
      "/users/agents/me/application/credentials",
      expect.objectContaining({ coverageStates: ["LAGOS"] }),
    );
  });

  it("submitApplication calls POST /users/agents/me/application/submit", async () => {
    const submitted = { ...mockApp, status: "PENDING" as AgentApplication["status"] };
    http.mock.post.mockResolvedValue({ data: submitted });
    const result = await service.submitApplication({
      truthfulnessAcknowledged: true,
      agentTermsConsentVersion: "1.0.0",
    });
    expect(http.mock.post).toHaveBeenCalledWith(
      "/users/agents/me/application/submit",
      { truthfulnessAcknowledged: true, agentTermsConsentVersion: "1.0.0" },
    );
    expect(result.data?.status).toBe("PENDING");
  });

  it("verifyBvn returns failure reason when verification fails", async () => {
    const bvnResult: BvnVerificationResult = {
      verified: false,
      bvnLast4: "",
      verificationId: null,
      failureReason: "BVN not found in database",
    };
    http.mock.post.mockResolvedValue({ data: bvnResult });
    const result = await service.verifyBvn({ bvn: "00000000000" });
    expect(result.data?.verified).toBe(false);
    expect(result.data?.failureReason).toBe("BVN not found in database");
  });
});

import type { HttpClient } from "@lib/FetchHttpClient";
import { httpClient } from "@/containers";
import { PublicVerificationSummary } from "../models";

export class PublicVerificationService {
  constructor(private readonly http: HttpClient) {}

  async getSummary(vid: string): Promise<PublicVerificationSummary | null> {
    try {
      const res = await this.http.get<{ data: PublicVerificationSummary }>(
        `/public/verifications/${vid}`,
        { cache: "no-store" }
      );
      return res?.data ?? null;
    } catch {
      return null;
    }
  }
}

export const publicVerificationService = new PublicVerificationService(httpClient);

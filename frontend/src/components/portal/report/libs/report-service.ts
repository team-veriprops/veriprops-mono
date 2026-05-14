import type { HttpClient } from "@lib/FetchHttpClient";
import { httpClient } from "@/containers";

export class ReportService {
  constructor(private readonly http: HttpClient) {}

  acknowledge(vid: string): Promise<void> {
    return this.http.post(`/portal/verifications/${vid}/report/acknowledge`, { ip_address: null });
  }

  downloadPdf(id: string): Promise<Blob> {
    return this.http.getBlob(`/portal/verifications/${id}/report/pdf`);
  }
}

export const reportService = new ReportService(httpClient);

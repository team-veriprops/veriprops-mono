import { QueryBankDto, SearchBankDto, CreateBankDto, UpdateBankDto } from "../models";
import { Page, SuccessResponse } from "@/types/models";
import { toQueryParams } from "@lib/utils";
import { HttpClient } from "@lib/FetchHttpClient";

export class BankService {
  bankBaseUrl: string;
  constructor(private readonly http: HttpClient) {
    this.bankBaseUrl = "/banks";
  }

  async createBank(payload: CreateBankDto): Promise<SuccessResponse<QueryBankDto>> {
    return await this.http.post<CreateBankDto, SuccessResponse<QueryBankDto>>(
      `${this.bankBaseUrl}`,
      payload
    );
  }

  async getBank(bankId: string): Promise<SuccessResponse<QueryBankDto>> {
    return this.http.get<SuccessResponse<QueryBankDto>>(
      `${this.bankBaseUrl}/${bankId}`,
    );
  }

  async searchBankPage(payload: SearchBankDto): Promise<Page<QueryBankDto>> {
    const query = toQueryParams(payload);
    return await this.http.get<Page<QueryBankDto>>(
      `${this.bankBaseUrl}?${query}`
    );
  }

  async updateBank(bankId: string, payload: UpdateBankDto): Promise<SuccessResponse<QueryBankDto>> {
    return this.http.put<UpdateBankDto, SuccessResponse<QueryBankDto>>(
      `${this.bankBaseUrl}/${bankId}`,
      payload
    );
  }

  async deactivateBank(bankId: string): Promise<boolean> {
    return this.http.patch<boolean>(
      `${this.bankBaseUrl}/${bankId}/deactivate`
    );
  }

  async activateBank(bankId: string): Promise<boolean> {
    return this.http.patch<boolean>(
      `${this.bankBaseUrl}/${bankId}/activate`
    );
  }

  async deleteBank(bankId: string): Promise<SuccessResponse<QueryBankDto>> {
    return this.http.delete<SuccessResponse<QueryBankDto>>(`${this.bankBaseUrl}/${bankId}`);
  }
}

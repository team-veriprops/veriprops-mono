import { HttpClient } from "@lib/FetchHttpClient";
import { Page, SuccessResponse } from "@/types/models";
import { AddBankAccountRequest, BankAccount, Payout, RequestPayoutRequest } from "@/types/payout";

/**
 * Agent payout API (PRD §15.1). Mirrors the agent routes in app/domain/payout/controller.py.
 */
export class PayoutService {
  constructor(private readonly http: HttpClient) {}

  listPayouts(page = 0, pageSize = 10): Promise<SuccessResponse<Page<Payout>>> {
    return this.http.get(`/agents/payouts?page=${page}&page_size=${pageSize}`);
  }

  requestPayout(req: RequestPayoutRequest): Promise<SuccessResponse<Payout>> {
    return this.http.post(`/agents/payouts`, req);
  }

  cancelPayout(payoutId: string): Promise<SuccessResponse<Payout>> {
    return this.http.post(`/agents/payouts/${payoutId}/cancel`);
  }

  listBankAccounts(): Promise<SuccessResponse<BankAccount[]>> {
    return this.http.get(`/agents/payouts/bank-accounts`);
  }

  addBankAccount(req: AddBankAccountRequest): Promise<SuccessResponse<BankAccount>> {
    return this.http.post(`/agents/payouts/bank-accounts`, req);
  }

  removeBankAccount(accountId: string): Promise<SuccessResponse<boolean>> {
    return this.http.delete(`/agents/payouts/bank-accounts/${accountId}`);
  }
}

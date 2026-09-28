import { HttpClient } from "@lib/FetchHttpClient";
import { DEFAULT_PAGE_SIZE } from "@lib/config/app";
import { Page, SuccessResponse } from "@/types/models";
import {
  AddBankAccountRequest,
  Bank,
  BankAccount,
  Payout,
  PayoutQuote,
  QuotePayoutRequest,
  RequestPayoutRequest,
  ResolveBankAccountRequest,
  ResolvedBankAccount,
} from "@/types/payout";

/**
 * Agent payout API (PRD §15.1). Mirrors the agent routes in app/domain/payout/controller.py.
 */
export class PayoutService {
  constructor(private readonly http: HttpClient) {}

  listPayouts(page = 0, pageSize = DEFAULT_PAGE_SIZE): Promise<SuccessResponse<Page<Payout>>> {
    return this.http.get(`/agents/payouts?page=${page}&page_size=${pageSize}`);
  }

  /** The transfer fee on a withdrawal to one of the agent's accounts, and what reaches the bank. */
  quotePayout(req: QuotePayoutRequest): Promise<SuccessResponse<PayoutQuote>> {
    return this.http.post(`/agents/payouts/quote`, req);
  }

  requestPayout(req: RequestPayoutRequest): Promise<SuccessResponse<Payout>> {
    return this.http.post(`/agents/payouts`, req);
  }

  cancelPayout(payoutId: string): Promise<SuccessResponse<Payout>> {
    return this.http.post(`/agents/payouts/${payoutId}/cancel`);
  }

  /** The banks an account can be saved with — the paying gateway's own list. */
  listBanks(): Promise<SuccessResponse<Bank[]>> {
    return this.http.get(`/agents/payouts/banks`);
  }

  /** The name the bank holds for an account, shown before it is saved. */
  resolveBankAccount(req: ResolveBankAccountRequest): Promise<SuccessResponse<ResolvedBankAccount>> {
    return this.http.post(`/agents/payouts/bank-accounts/resolve`, req);
  }

  listBankAccounts(): Promise<SuccessResponse<BankAccount[]>> {
    return this.http.get(`/agents/payouts/bank-accounts`);
  }

  /** Save an account. The backend resolves its name again; the client never sends one. */
  addBankAccount(req: AddBankAccountRequest): Promise<SuccessResponse<BankAccount>> {
    return this.http.post(`/agents/payouts/bank-accounts`, req);
  }

  removeBankAccount(accountId: string): Promise<SuccessResponse<boolean>> {
    return this.http.delete(`/agents/payouts/bank-accounts/${accountId}`);
  }
}

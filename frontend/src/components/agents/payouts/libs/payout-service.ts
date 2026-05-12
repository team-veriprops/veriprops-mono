import { httpClient } from "@/containers";

export interface BankAccount {
  id: string;
  agentId: string;
  bankName: string;
  accountNumber: string;
  accountHolderName: string;
  isDefault: boolean;
  dateCreated: string;
}

export interface Payout {
  id: string;
  agentId: string;
  amount: number;
  bankAccountId: string;
  status: string;
  requestedAt: string;
  approvedAt: string | null;
  paidAt: string | null;
  holdReason: string | null;
  dateCreated: string;
}

export interface CreateBankAccountDto {
  bankName: string;
  accountNumber: string;
  accountHolderName: string;
  isDefault?: boolean;
}

export class PayoutService {
  listBankAccounts(): Promise<{ data: BankAccount[] }> {
    return httpClient.get("/api/agent/bank-accounts");
  }

  addBankAccount(dto: CreateBankAccountDto): Promise<{ data: BankAccount }> {
    return httpClient.post("/api/agent/bank-accounts", dto);
  }

  requestWithdrawal(amount: number, bankAccountId: string): Promise<{ data: Payout }> {
    return httpClient.post("/api/agent/payouts", { amount, bankAccountId });
  }

  listPayouts(): Promise<{ data: Payout[] }> {
    return httpClient.get("/api/agent/payouts");
  }
}

export class PayoutAdminService {
  listAll(): Promise<{ data: Payout[] }> {
    return httpClient.get("/api/admin/payouts");
  }

  approve(payoutId: string): Promise<{ data: Payout }> {
    return httpClient.post(`/api/admin/payouts/${payoutId}/approve`);
  }

  hold(payoutId: string, reason: string): Promise<{ data: Payout }> {
    return httpClient.post(`/api/admin/payouts/${payoutId}/hold`, { reason });
  }

  adjust(payoutId: string, newAmount: number, reason: string): Promise<{ data: Payout }> {
    return httpClient.put(`/api/admin/payouts/${payoutId}/adjust`, { newAmount, reason });
  }
}

export const payoutService = new PayoutService();
export const payoutAdminService = new PayoutAdminService();

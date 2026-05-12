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
    return httpClient.get("/agent/bank-accounts");
  }

  addBankAccount(dto: CreateBankAccountDto): Promise<{ data: BankAccount }> {
    return httpClient.post("/agent/bank-accounts", dto);
  }

  requestWithdrawal(amount: number, bankAccountId: string): Promise<{ data: Payout }> {
    return httpClient.post("/agent/payouts", { amount, bankAccountId });
  }

  listPayouts(): Promise<{ data: Payout[] }> {
    return httpClient.get("/agent/payouts");
  }
}

export class PayoutAdminService {
  listAll(): Promise<{ data: Payout[] }> {
    return httpClient.get("/admin/payouts");
  }

  approve(payoutId: string): Promise<{ data: Payout }> {
    return httpClient.post(`/admin/payouts/${payoutId}/approve`);
  }

  hold(payoutId: string, reason: string): Promise<{ data: Payout }> {
    return httpClient.post(`/admin/payouts/${payoutId}/hold`, { reason });
  }

  adjust(payoutId: string, newAmount: number, reason: string): Promise<{ data: Payout }> {
    return httpClient.put(`/admin/payouts/${payoutId}/adjust`, { newAmount, reason });
  }
}

export const payoutService = new PayoutService();
export const payoutAdminService = new PayoutAdminService();

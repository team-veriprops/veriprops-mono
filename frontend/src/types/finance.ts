// Finance summary types — mirror backend camelCase DTO (PRD §18.1).

export interface FinanceSummary {
  revenueMinor: number;
  paymentsByStatus: Record<string, number>;
  commissionsByStatus: Record<string, number>;
  payoutsByStatus: Record<string, number>;
  pendingPayouts: number;
}

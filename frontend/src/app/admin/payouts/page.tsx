import PayoutPanel from "@components/admin/payouts/PayoutPanel";

export const metadata = { title: "Payouts — Admin" };

export default function AdminPayoutsPage() {
  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <h1 className="text-xl font-semibold text-gray-900 mb-2">Payout Management</h1>
      <p className="text-sm text-gray-500 mb-6">
        Review, approve, hold, or adjust agent withdrawal requests.
      </p>
      <PayoutPanel />
    </div>
  );
}

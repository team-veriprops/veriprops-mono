import FraudFlagQueue from "@components/admin/fraud/FraudFlagQueue";

export const metadata = { title: "Fraud Flag Review — Veriprops Admin" };

export default function FraudFlagsPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-xl font-semibold text-gray-900 mb-6">Held Messages — Fraud Review</h1>
      <FraudFlagQueue />
    </div>
  );
}

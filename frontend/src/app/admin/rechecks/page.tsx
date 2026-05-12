import RecheckQueue from "@components/admin/rechecks/RecheckQueue";

export const metadata = { title: "Re-check Requests — Admin" };

export default function AdminRechecksPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-xl font-semibold text-gray-900 mb-6">Re-check Requests</h1>
      <RecheckQueue />
    </div>
  );
}

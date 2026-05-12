import DisputeQueue from "@components/admin/disputes/DisputeQueue";

export const metadata = { title: "Disputes — Admin" };

export default function AdminDisputesPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-xl font-semibold text-gray-900 mb-6">Disputes</h1>
      <DisputeQueue />
    </div>
  );
}

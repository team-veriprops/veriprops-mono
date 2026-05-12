import CommissionRuleEditor from "@components/admin/commission/CommissionRuleEditor";

export const metadata = { title: "Commission Rules — Admin" };

export default function AdminCommissionRulesPage() {
  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-xl font-semibold text-gray-900 mb-2">Commission Rules</h1>
      <p className="text-sm text-gray-500 mb-6">
        Configure the percentage commission agents earn per verification tier and role.
      </p>
      <CommissionRuleEditor />
    </div>
  );
}

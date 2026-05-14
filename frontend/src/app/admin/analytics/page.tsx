import AnalyticsDashboard from "@components/admin/analytics/AnalyticsDashboard";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Analytics | Veriprops Admin",
};

export default function AnalyticsPage() {
  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">
      <AnalyticsDashboard />
    </div>
  );
}

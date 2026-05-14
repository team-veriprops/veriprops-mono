import type { Metadata } from "next";
import PricingManager from "@components/admin/pricing/PricingManager";
import UpgradeDeltaEditor from "@components/admin/pricing/UpgradeDeltaEditor";

export const metadata: Metadata = {
  title: "Pricing | Veriprops Admin",
};

export default function PricingPage() {
  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto space-y-10">
      <PricingManager />
      <UpgradeDeltaEditor />
    </div>
  );
}

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import ContentItemTable from "@components/admin/content/ContentItemTable";
import AreaInsightPanel from "@components/admin/content/AreaInsightPanel";
import ContentItemForm from "@components/admin/content/ContentItemForm";
import type { ContentItemType } from "@components/admin/libs/admin-service";

type Tab = {
  key: ContentItemType | "area-insights";
  label: string;
  itemType?: ContentItemType;
};

const TABS: Tab[] = [
  { key: "HOW_IT_WORKS_STEP", label: "How It Works", itemType: "HOW_IT_WORKS_STEP" },
  { key: "FAQ", label: "FAQs", itemType: "FAQ" },
  { key: "TESTIMONIAL", label: "Testimonials", itemType: "TESTIMONIAL" },
  { key: "AGENT_SPOTLIGHT", label: "Agent Spotlights", itemType: "AGENT_SPOTLIGHT" },
  { key: "area-insights", label: "Area Insights" },
];

export default function ContentPage() {
  const [activeTab, setActiveTab] = useState<Tab["key"]>("HOW_IT_WORKS_STEP");
  const [showNew, setShowNew] = useState(false);

  const currentTab = TABS.find((t) => t.key === activeTab)!;

  if (showNew) {
    return (
      <div className="p-6 lg:p-8 max-w-3xl mx-auto">
        <ContentItemForm
          defaultType={currentTab.itemType ?? "FAQ"}
          onClose={() => setShowNew(false)}
        />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold" style={{ color: "var(--brand-navy)" }}>Content Management</h1>
        <button
          type="button"
          onClick={() => setShowNew(true)}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white"
          style={{ background: "var(--brand-viridian)" }}
        >
          + New Item
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-xl" style={{ background: "rgba(63,102,83,0.06)" }}>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className="flex-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
            style={{
              background: activeTab === tab.key ? "white" : "transparent",
              color: activeTab === tab.key ? "var(--brand-navy)" : "var(--brand-on-surface-variant)",
              boxShadow: activeTab === tab.key ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {activeTab === "area-insights" ? (
        <AreaInsightPanel />
      ) : (
        <ContentItemTable itemType={currentTab.itemType} />
      )}
    </div>
  );
}

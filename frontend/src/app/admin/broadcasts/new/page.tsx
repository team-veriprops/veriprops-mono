import { Metadata } from "next";
import Link from "next/link";
import BroadcastComposer from "@components/admin/broadcast/BroadcastComposer";
import { ROUTES } from "@lib/routes";

export const metadata: Metadata = {
  title: "New Broadcast | Veriprops Admin",
};

export default function NewBroadcastPage() {
  return (
    <div className="p-6 lg:p-8 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href={ROUTES.ADMIN.BROADCASTS}
          className="text-sm"
          style={{ color: "var(--brand-on-surface-variant)" }}
        >
          ← Broadcasts
        </Link>
        <h1 className="text-xl font-semibold" style={{ color: "var(--brand-navy)" }}>New Broadcast</h1>
      </div>
      <BroadcastComposer />
    </div>
  );
}

import { Metadata } from "next";
import Link from "next/link";
import BroadcastList from "@components/admin/broadcast/BroadcastList";
import { ROUTES } from "@lib/routes";

export const metadata: Metadata = {
  title: "Broadcasts | Veriprops Admin",
};

export default function BroadcastsPage() {
  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold" style={{ color: "var(--brand-navy)" }}>Broadcasts</h1>
        <Link
          href={ROUTES.ADMIN.BROADCAST_NEW}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white inline-block"
          style={{ background: "var(--brand-viridian)" }}
        >
          + New Broadcast
        </Link>
      </div>
      <BroadcastList />
    </div>
  );
}

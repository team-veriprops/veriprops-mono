"use client";

import { Loader2, Monitor, Smartphone, LogOut } from "lucide-react";
import AccountShell from "./AccountShell";
import { Button } from "@3rdparty/ui/button";
import {
  useDevicesQuery,
  useRevokeAllOtherDevicesMutation,
  useRevokeDeviceMutation,
} from "@components/website/auth/libs/useAuthQueries";
import { DeviceSession } from "@components/website/auth/models";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";

export default function DevicesContainer() {
  const devicesQuery = useDevicesQuery();
  const revokeOne = useRevokeDeviceMutation();
  const revokeAllOthers = useRevokeAllOtherDevicesMutation();
  const devices = devicesQuery.data ?? [];

  return (
    <AccountShell
      title="Connected devices"
      subtitle="Every device currently signed in to your Veriprops account. Don't recognise one? Revoke it immediately and reset your password."
    >
      <div className="flex justify-end mb-4">
        <Button
          variant="outline"
          size="sm"
          disabled={revokeAllOthers.isPending || devices.filter((d) => !d.current).length === 0}
          onClick={() =>
            revokeAllOthers.mutate(undefined, {
              onSuccess: () => toast.success("Signed out from all other devices."),
              onError: () => toast.error("Could not sign out other devices."),
            })
          }
        >
          <LogOut className="w-4 h-4" />
          Sign out from all others
        </Button>
      </div>

      {devicesQuery.isLoading ? (
        <Loading />
      ) : devices.length === 0 ? (
        <EmptyState />
      ) : (
        <ul className="space-y-3">
          {devices.map((d) => (
            <DeviceRow
              key={d.id}
              device={d}
              onRevoke={() =>
                revokeOne.mutate(d.id, {
                  onSuccess: () => toast.success(`Signed ${d.device} out.`),
                  onError: () => toast.error("Could not revoke device."),
                })
              }
              loading={revokeOne.isPending}
            />
          ))}
        </ul>
      )}
    </AccountShell>
  );
}

function Loading() {
  return (
    <div className="flex items-center justify-center py-16">
      <Loader2 className="w-6 h-6 animate-spin" style={{ color: "var(--brand-viridian)" }} />
    </div>
  );
}

function EmptyState() {
  return (
    <div
      className="rounded-xl p-10 text-center"
      style={{ backgroundColor: "var(--brand-surface-card)", boxShadow: "var(--shadow-card)" }}
    >
      <Monitor className="w-10 h-10 mx-auto mb-4" style={{ color: "var(--brand-viridian)" }} />
      <p className="text-base font-semibold" style={{ color: "var(--brand-navy)" }}>
        No active sessions
      </p>
      <p className="text-sm mt-1.5" style={{ color: "var(--brand-on-surface-variant)" }}>
        Sign in on a device to see it listed here.
      </p>
    </div>
  );
}

function DeviceRow({
  device,
  onRevoke,
  loading,
}: {
  device: DeviceSession;
  onRevoke: () => void;
  loading: boolean;
}) {
  const Icon = device.device.toLowerCase().includes("phone") ? Smartphone : Monitor;
  return (
    <li
      className="flex items-start gap-4 p-5 rounded-xl"
      style={{ backgroundColor: "var(--brand-surface-card)", boxShadow: "var(--shadow-card)" }}
    >
      <span
        className="w-11 h-11 rounded-lg flex items-center justify-center shrink-0"
        style={{
          backgroundColor: "rgba(63,102,83,0.1)",
          color: "var(--brand-viridian)",
        }}
      >
        <Icon className="w-5 h-5" />
      </span>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
            {device.device} · {device.browser}
          </p>
          {device.current && (
            <span
              className="text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full"
              style={{
                backgroundColor: "rgba(63,102,83,0.12)",
                color: "var(--brand-viridian)",
              }}
            >
              This device
            </span>
          )}
        </div>
        <div
          className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs"
          style={{ color: "var(--brand-on-surface-variant)" }}
        >
          <span>{device.os}</span>
          <span>· {device.approxLocation}</span>
          <span>· IP {device.ipAddress}</span>
          <span>· active {formatRelative(device.lastActiveAt)}</span>
        </div>
      </div>

      {!device.current && (
        <Button variant="outline" size="sm" disabled={loading} onClick={onRevoke}>
          Revoke
        </Button>
      )}
    </li>
  );
}

function formatRelative(iso: string): string {
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true });
  } catch {
    return iso;
  }
}

"use client";

import { Loader2, Monitor, LogOut } from "lucide-react";
import { toast } from "sonner";

import {
  useDevicesQuery,
  useRevokeDeviceMutation,
  useRevokeAllOtherDevicesMutation,
} from "@components/website/auth/libs/useAuthQueries";
import { Button } from "@3rdparty/ui/button";

export default function ConnectedDevicesPage() {
  const { data: devices = [], isLoading, isError } = useDevicesQuery();
  const revoke = useRevokeDeviceMutation();
  const revokeAllOthers = useRevokeAllOtherDevicesMutation();

  const hasOthers = devices.some((d) => !d.current);

  return (
    <div className="max-w-4xl mx-auto px-4 md:px-8 py-8" data-testid="devices">
      <header className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-brand-navy">
            Connected Devices
          </h1>
          <p className="text-sm mt-1 text-brand-on-surface-variant">
            Devices currently signed in to your account. Revoke any you don&rsquo;t recognise.
          </p>
        </div>
        {hasOthers && (
          <Button
            variant="outline"
            disabled={revokeAllOthers.isPending}
            data-testid="devices-logout-others"
            onClick={() =>
              revokeAllOthers.mutate(undefined, {
                onSuccess: () => toast.success("Signed out of all other devices."),
                onError: () => toast.error("Could not sign out other devices."),
              })
            }
          >
            <LogOut className="w-4 h-4 mr-1.5" /> Log out all others
          </Button>
        )}
      </header>

      {isLoading ? (
        <div className="flex items-center gap-2 py-12 justify-center text-brand-on-surface-variant">
          <Loader2 className="w-5 h-5 animate-spin" /> Loading devices…
        </div>
      ) : isError ? (
        <p className="py-12 text-center text-sm text-danger">
          Could not load your devices. Please try again.
        </p>
      ) : (
        <ul className="space-y-2" data-testid="devices-list">
          {devices.map((d) => (
            <li
              key={d.id}
              data-testid="device-row"
              className="flex items-center gap-3 rounded-xl p-4 bg-brand-surface-card shadow-card"
            >
              <span
                className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 bg-brand-surface-high text-brand-navy"
              >
                <Monitor className="w-5 h-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold flex items-center gap-2 text-brand-navy">
                  {d.device || "Unknown device"}
                  {d.current && (
                    <span
                      className="text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded bg-brand-viridian-xlight text-brand-viridian"
                      data-testid="device-current-badge"
                    >
                      This device
                    </span>
                  )}
                </p>
                <p className="text-xs mt-1 text-brand-on-surface-variant">
                  {[d.ipAddress, d.approxLocation].filter(Boolean).join(" · ")}
                  {d.lastActiveAt ? ` · active ${new Date(d.lastActiveAt).toLocaleDateString()}` : ""}
                </p>
              </div>
              {!d.current && (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={revoke.isPending}
                  data-testid="device-revoke"
                  onClick={() =>
                    revoke.mutate(d.id, {
                      onSuccess: () => toast.success("Device signed out."),
                      onError: () => toast.error("Could not revoke device."),
                    })
                  }
                  className="text-danger"
                >
                  Revoke
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

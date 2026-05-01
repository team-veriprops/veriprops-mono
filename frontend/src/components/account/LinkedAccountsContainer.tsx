"use client";

import { useState } from "react";
import Link from "next/link";
import { Loader2, Link2, AlertTriangle } from "lucide-react";
import AccountShell from "./AccountShell";
import { Button } from "@3rdparty/ui/button";
import {
  useLinkedProvidersQuery,
  useUnlinkProviderMutation,
} from "@components/website/auth/libs/useAuthQueries";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";
import { OAuthFlowMode, SocialProvider } from "@components/website/auth/models";
import { startOauthPopup } from "@components/website/auth/libs/auth/oauthPopup";
import { ROUTES } from "@lib/routes";
import { toast } from "sonner";

const PROVIDERS: { id: SocialProvider; name: string; available: boolean }[] = [
  { id: SocialProvider.GOOGLE,   name: "Google",   available: true },
  { id: SocialProvider.APPLE,    name: "Apple",    available: true },
  { id: SocialProvider.FACEBOOK, name: "Facebook", available: true },
];

export default function LinkedAccountsContainer() {
  const linkedQuery = useLinkedProvidersQuery();
  const unlink = useUnlinkProviderMutation();
  const linked = linkedQuery.data ?? [];
  const session = useAuthStore((s) => s.session);
  const hasPassword = session?.user?.hasPassword ?? false;
  const [linkPending, setLinkPending] = useState<SocialProvider | null>(null);

  const startLink = (provider: SocialProvider, name: string) => {
    setLinkPending(provider);
    startOauthPopup(provider, {
      mode: OAuthFlowMode.LINK,
      onSuccess: () => {
        setLinkPending(null);
        toast.success(`Linked ${name}.`);
        linkedQuery.refetch();
      },
      onCancel: () => setLinkPending(null),
      onError: (err) => {
        setLinkPending(null);
        if (err.code === "popup_blocked") {
          toast.error("Popup blocked. Allow popups and try again.");
          return;
        }
        toast.error(err.message ?? `Could not link ${name}.`);
      },
    });
  };

  return (
    <AccountShell
      title="Linked accounts"
      subtitle="Sign in faster with your social account, and unlink whenever you want — as long as you have a password set."
    >
      {!hasPassword && (
        <div
          className="mb-6 p-4 rounded-xl flex items-start gap-3"
          style={{
            backgroundColor: "rgba(176,125,0,0.06)",
            border: "1px solid rgba(176,125,0,0.2)",
            color: "var(--warning)",
          }}
        >
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="text-sm leading-relaxed">
            <strong className="block">Set a password before unlinking.</strong>
            Without a password you wouldn&apos;t be able to sign in if your social provider is
            unavailable.{" "}
            <Link
              href={ROUTES.AUTH.SET_PASSWORD}
              className="underline font-semibold"
              style={{ color: "var(--warning)" }}
            >
              Set a password
            </Link>
          </div>
        </div>
      )}

      {linkedQuery.isLoading ? (
        <Loading />
      ) : (
        <ul className="space-y-3">
          {PROVIDERS.map((p) => {
            const isLinked = linked.includes(p.id);
            return (
              <li
                key={p.id}
                className="flex items-center justify-between gap-4 p-5 rounded-xl"
                style={{ backgroundColor: "var(--brand-surface-card)", boxShadow: "var(--shadow-card)" }}
              >
                <div className="flex items-center gap-4">
                  <span
                    className="w-11 h-11 rounded-lg flex items-center justify-center"
                    style={{
                      backgroundColor: "rgba(0,13,34,0.05)",
                      color: "var(--brand-navy)",
                    }}
                  >
                    <Link2 className="w-5 h-5" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
                      {p.name}
                    </p>
                    <p className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
                      {p.available
                        ? isLinked
                          ? "Connected"
                          : "Not connected"
                        : "Coming soon"}
                    </p>
                  </div>
                </div>
                {p.available &&
                  (isLinked ? (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={unlink.isPending || !hasPassword}
                      onClick={() =>
                        unlink.mutate(p.id, {
                          onSuccess: () => toast.success(`Unlinked ${p.name}.`),
                          onError: () => toast.error(`Could not unlink ${p.name}.`),
                        })
                      }
                    >
                      Unlink
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      disabled={linkPending !== null}
                      onClick={() => startLink(p.id, p.name)}
                    >
                      {linkPending === p.id ? "Opening…" : "Link account"}
                    </Button>
                  ))}
              </li>
            );
          })}
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

"use client";

import { useState } from "react";
import { Loader2, Link2, Unlink } from "lucide-react";
import { toast } from "sonner";

import {
  useLinkedProvidersQuery,
  useUnlinkProviderMutation,
  useCurrentSession,
  authKeys,
} from "@components/website/auth/libs/useAuthQueries";
import { startOauthPopup } from "@components/website/auth/libs/auth/oauthPopup";
import { OAuthFlowMode, SocialProvider } from "@components/website/auth/models";
import { Button } from "@3rdparty/ui/button";
import { useQueryClient } from "@tanstack/react-query";

const PROVIDERS: { id: SocialProvider; label: string }[] = [
  { id: SocialProvider.GOOGLE, label: "Google" },
  { id: SocialProvider.APPLE, label: "Apple" },
  { id: SocialProvider.FACEBOOK, label: "Facebook" },
];

export default function LinkedAccountsPage() {
  const qc = useQueryClient();
  const { data: linked = [], isLoading, isError } = useLinkedProvidersQuery();
  const unlink = useUnlinkProviderMutation();
  const sessionQuery = useCurrentSession();
  const [pending, setPending] = useState<SocialProvider | null>(null);

  const linkProvider = (provider: SocialProvider) => {
    if (typeof window === "undefined") return;
    setPending(provider);
    startOauthPopup(provider, {
      mode: OAuthFlowMode.LINK,
      onSuccess: async () => {
        setPending(null);
        await qc.invalidateQueries({ queryKey: authKeys.linked });
        await sessionQuery.refetch();
        toast.success("Account linked.");
      },
      onCancel: () => setPending(null),
      onError: (err) => {
        setPending(null);
        toast.error(err.message ?? "Could not link this account.");
      },
    });
  };

  return (
    <div className="max-w-4xl mx-auto px-4 md:px-8 py-8" data-testid="linked-accounts">
      <header className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: "var(--brand-navy)" }}>
          Linked Accounts
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Connect a social account for faster sign-in. You can&rsquo;t unlink your only
          sign-in method until you set a password.
        </p>
      </header>

      {isLoading ? (
        <div className="flex items-center gap-2 py-12 justify-center" style={{ color: "var(--brand-on-surface-variant)" }}>
          <Loader2 className="w-5 h-5 animate-spin" /> Loading…
        </div>
      ) : isError ? (
        <p className="py-12 text-center text-sm" style={{ color: "var(--brand-destructive, #ba1a1a)" }}>
          Could not load your linked accounts. Please try again.
        </p>
      ) : (
        <ul className="space-y-2" data-testid="linked-accounts-list">
          {PROVIDERS.map(({ id, label }) => {
            const isLinked = linked.includes(id);
            const isPending = pending === id || (unlink.isPending && unlink.variables === id);
            return (
              <li
                key={id}
                data-testid={`linked-row-${id}`}
                data-linked={isLinked}
                className="flex items-center gap-3 rounded-xl p-4"
                style={{ backgroundColor: "var(--brand-surface-card)", boxShadow: "0 1px 3px rgba(0,13,34,0.06)" }}
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>{label}</p>
                  <p className="text-xs mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
                    {isLinked ? "Connected" : "Not connected"}
                  </p>
                </div>
                {isLinked ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={isPending}
                    data-testid={`linked-unlink-${id}`}
                    style={{ color: "var(--brand-destructive, #ba1a1a)" }}
                    onClick={() =>
                      unlink.mutate(id, {
                        onSuccess: () => toast.success(`${label} unlinked.`),
                        onError: () =>
                          toast.error(
                            "Could not unlink. Set a password first if this is your only sign-in method.",
                          ),
                      })
                    }
                  >
                    <Unlink className="w-4 h-4 mr-1.5" /> Unlink
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={isPending}
                    data-testid={`linked-link-${id}`}
                    onClick={() => linkProvider(id)}
                  >
                    <Link2 className="w-4 h-4 mr-1.5" /> Link
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

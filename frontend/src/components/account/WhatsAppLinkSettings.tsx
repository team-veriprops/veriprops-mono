"use client";

import { useState } from "react";
import { Loader2, MessageCircle, ShieldCheck, Unlink } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@3rdparty/ui/button";
import PhoneInputWithCountry from "@components/ui/form/PhoneInputWithCountry";
import { DEFAULT_COUNTRY_CODE, DEFAULT_DIAL_CODE } from "@lib/config/app";
import { getErrorMessage } from "@lib/utils";
import { WhatsAppLinkStatus } from "@/types/whatsappLink";
import {
  useConfirmWhatsAppLinkMutation,
  useStartWhatsAppLinkMutation,
  useUnlinkWhatsAppMutation,
  useWhatsAppLinkQuery,
} from "./libs/useWhatsAppLinkQueries";

/**
 * Account → WhatsApp (PRD §7.4.4, WA-23/WA-25).
 *
 * Linking a number is what lets the bot say anything about a case at all, so this page
 * is deliberately explicit about the consequences rather than presenting a toggle:
 *
 * * **Only ACTIVE means linked.** A number sitting on a pending row grants nothing, so
 *   the page renders the backend's status instead of inferring "linked" from a number
 *   being present.
 * * **Changing the number is a re-verification, not an edit.** The old number stops
 *   resolving the moment a new one is claimed, and the copy says so before the customer
 *   starts.
 * * **Unlinking is stated in terms of what it does** — the WhatsApp thread goes cold —
 *   because "unlink" alone does not tell anyone their chat will stop answering.
 */
export default function WhatsAppLinkSettings() {
  const { data: link, isLoading, isError } = useWhatsAppLinkQuery();
  const startLink = useStartWhatsAppLinkMutation();
  const confirmLink = useConfirmWhatsAppLinkMutation();
  const unlink = useUnlinkWhatsAppMutation();

  const [countryCode, setCountryCode] = useState(DEFAULT_COUNTRY_CODE);
  const [dialCode, setDialCode] = useState(DEFAULT_DIAL_CODE);
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  // Set once a code has been sent: this is the number the code was sent *to*, and it is
  // what confirmation submits — not whatever the input holds by then.
  const [pendingNumber, setPendingNumber] = useState<string | null>(null);
  const [changing, setChanging] = useState(false);

  const isLinked = link?.status === WhatsAppLinkStatus.ACTIVE && !!link.phoneE164;

  const onSend = async () => {
    try {
      const challenge = await startLink.mutateAsync(toE164(dialCode, phone));
      setPendingNumber(challenge?.phoneE164 ?? null);
      toast.success("We sent a code to that number on WhatsApp.");
    } catch (err) {
      toast.error(getErrorMessage(err as Error, "Could not send the code."));
    }
  };

  const onConfirm = async () => {
    if (!pendingNumber) return;
    try {
      await confirmLink.mutateAsync({ phoneE164: pendingNumber, code });
      setPendingNumber(null);
      setCode("");
      setChanging(false);
      toast.success("WhatsApp number linked.");
    } catch (err) {
      toast.error(getErrorMessage(err as Error, "That code didn't match. Try again."));
    }
  };

  const onUnlink = async () => {
    try {
      await unlink.mutateAsync();
      setChanging(false);
      toast.success("WhatsApp number unlinked.");
    } catch (err) {
      toast.error(getErrorMessage(err as Error, "Could not unlink that number."));
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 md:px-8 py-8" data-testid="wa-link-settings">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-brand-navy">WhatsApp</h1>
        <p className="text-sm mt-1 text-brand-on-surface-variant">
          Link your WhatsApp number so our assistant can recognise you and answer
          questions about your verifications. Until a number is linked, it is never told
          anything about your cases.
        </p>
      </header>

      {isLoading ? (
        <div className="flex items-center gap-2 py-12 justify-center text-brand-on-surface-variant">
          <Loader2 className="w-5 h-5 animate-spin" /> Loading…
        </div>
      ) : isError ? (
        <p className="py-12 text-center text-sm text-destructive">
          Could not load your WhatsApp settings. Please try again.
        </p>
      ) : isLinked && !changing ? (
        <LinkedCard
          number={link!.phoneE164!}
          onChange={() => {
            setChanging(true);
            setPendingNumber(null);
          }}
          onUnlink={onUnlink}
          unlinking={unlink.isPending}
        />
      ) : (
        <div className="rounded-xl p-5 bg-brand-surface-card shadow-card space-y-4">
          {changing && (
            <p className="text-sm text-brand-on-surface-variant" data-testid="wa-link-change-notice">
              Changing your number means verifying the new one. The old number stops
              receiving updates about your verifications straight away.
            </p>
          )}

          {!pendingNumber ? (
            <>
              <label className="text-sm font-medium text-foreground">WhatsApp number</label>
              <PhoneInputWithCountry
                countryCode={countryCode}
                phone={phone}
                placeholder="0801 234 5678"
                disabled={startLink.isPending}
                data-testid="wa-link-phone"
                onChange={(next) => {
                  setCountryCode(next.countryCode);
                  setDialCode(next.dialCode);
                  setPhone(next.phone);
                }}
              />
              <div className="flex gap-2">
                <Button
                  onClick={onSend}
                  disabled={phone.length < 7 || startLink.isPending}
                  data-testid="wa-link-send"
                >
                  {startLink.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  Send code on WhatsApp
                </Button>
                {changing && (
                  <Button variant="ghost" onClick={() => setChanging(false)}>
                    Cancel
                  </Button>
                )}
              </div>
            </>
          ) : (
            <>
              <p className="text-sm text-brand-on-surface-variant">
                Enter the 6-digit code we sent to{" "}
                <span className="font-medium text-foreground">{pendingNumber}</span> on
                WhatsApp.
              </p>
              <input
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                placeholder="654123"
                data-testid="wa-link-code"
                className="flex h-10 w-40 rounded-md border border-input bg-background px-3 py-2 text-base outline-none focus:ring-2 focus:ring-ring md:text-sm"
              />
              <div className="flex gap-2">
                <Button
                  onClick={onConfirm}
                  disabled={code.length < 6 || confirmLink.isPending}
                  data-testid="wa-link-confirm"
                >
                  {confirmLink.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  Link this number
                </Button>
                <Button variant="ghost" onClick={() => setPendingNumber(null)}>
                  Use a different number
                </Button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function LinkedCard({
  number,
  onChange,
  onUnlink,
  unlinking,
}: {
  number: string;
  onChange: () => void;
  onUnlink: () => void;
  unlinking: boolean;
}) {
  const [confirming, setConfirming] = useState(false);

  return (
    <div className="rounded-xl p-5 bg-brand-surface-card shadow-card space-y-4" data-testid="wa-link-linked">
      <div className="flex items-start gap-3">
        <span className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 bg-brand-viridian-xlight text-brand-viridian">
          <MessageCircle className="w-5 h-5" />
        </span>
        <div>
          <p className="font-medium text-foreground" data-testid="wa-link-number">{number}</p>
          <p className="text-sm text-brand-on-surface-variant flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4" /> Verified — our assistant recognises this
            number.
          </p>
        </div>
      </div>

      {confirming ? (
        <div className="space-y-3 border-t pt-4">
          <p className="text-sm text-brand-on-surface-variant" data-testid="wa-unlink-warning">
            Unlinking stops this number receiving anything about your verifications. Your
            existing WhatsApp chat stays open, but the assistant will no longer recognise
            you there until you link a number again.
          </p>
          <div className="flex gap-2">
            <Button variant="destructive" onClick={onUnlink} disabled={unlinking} data-testid="wa-unlink-confirm">
              {unlinking && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Unlink
            </Button>
            <Button variant="ghost" onClick={() => setConfirming(false)}>
              Keep it linked
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2 border-t pt-4">
          <Button variant="outline" onClick={onChange} data-testid="wa-link-change">
            Change number
          </Button>
          <Button variant="ghost" onClick={() => setConfirming(true)} data-testid="wa-unlink">
            <Unlink className="w-4 h-4 mr-2" /> Unlink
          </Button>
        </div>
      )}
    </div>
  );
}

/** The dial code and national number as the backend keys identity on them. */
function toE164(dialCode: string, phone: string): string {
  const digits = `${dialCode}${phone}`.replace(/\D/g, "");
  return `+${digits}`;
}

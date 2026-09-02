"use client";

import { useState } from "react";
import { Loader2, ShieldCheck, UserPlus } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import PhoneInputWithCountry from "@components/ui/form/PhoneInputWithCountry";
import { DEFAULT_COUNTRY_CODE, DEFAULT_DIAL_CODE } from "@lib/config/app";
import { getErrorMessage } from "@lib/utils";
import { CaseDelegate } from "@/types/delegate";
import {
  useAuthorizeDelegateMutation,
  useConfirmDelegateMutation,
  useDelegatesQuery,
  useRevokeDelegateMutation,
} from "@components/portal/libs/useDelegateQueries";

/**
 * Authorize one person to follow this verification (PRD §7.4.5, Decision O).
 *
 * This panel exists so the bot can say *no* to everyone else without being useless. "My
 * relative is handling it" is a social-engineering script, and the only safe answer to it
 * is a refusal plus a legitimate route — which is this.
 *
 * The copy is explicit about how narrow the grant is, because that is what makes it safe
 * to offer: status milestones only, one person, and revocable in a click. A buyer who
 * believes they are sharing the report would be surprised twice — once here, and once
 * when their delegate asks why they cannot open it.
 *
 * It sits after "Your agents" and before "Evidence" on the case page: with the people on
 * the case, ahead of the material a delegate must never see.
 */
export default function DelegatePanel({ verificationId }: { verificationId: string }) {
  const { data: delegates, isLoading } = useDelegatesQuery(verificationId);
  const authorize = useAuthorizeDelegateMutation(verificationId);
  const confirm = useConfirmDelegateMutation(verificationId);
  const revoke = useRevokeDelegateMutation(verificationId);

  const [countryCode, setCountryCode] = useState(DEFAULT_COUNTRY_CODE);
  const [dialCode, setDialCode] = useState(DEFAULT_DIAL_CODE);
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");

  const delegate = delegates?.[0] ?? null;

  const onAuthorize = async () => {
    try {
      await authorize.mutateAsync({ name, phoneE164: toE164(dialCode, phone) });
      toast.success("We sent them a code on WhatsApp. Ask them to read it to you.");
    } catch (err) {
      toast.error(getErrorMessage(err as Error, "Could not authorize that delegate."));
    }
  };

  const onConfirm = async () => {
    try {
      await confirm.mutateAsync(code);
      setCode("");
      setName("");
      setPhone("");
      toast.success("Delegate confirmed — they'll get status updates from now on.");
    } catch (err) {
      toast.error(getErrorMessage(err as Error, "That code didn't match. Try again."));
    }
  };

  const onRevoke = async () => {
    try {
      await revoke.mutateAsync();
      toast.success("Delegate removed. They won't receive any further updates.");
    } catch (err) {
      toast.error(getErrorMessage(err as Error, "Could not remove that delegate."));
    }
  };

  return (
    <section
      className="rounded-xl bg-brand-surface-card p-5 shadow-card"
      data-testid="delegate-panel"
    >
      <h2 className="mb-1 text-base font-semibold text-brand-navy">
        Someone else following this
      </h2>
      <p className="mb-4 text-sm text-brand-on-surface-variant">
        You can authorize one person to receive progress updates on WhatsApp — a spouse,
        a relative, or the person helping you buy. They get{" "}
        <strong>status updates only</strong>: never your documents, your report, or this
        chat. You can remove them at any time.
      </p>

      {isLoading ? (
        <div className="flex items-center gap-2 py-6 text-brand-on-surface-variant">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : delegate ? (
        <DelegateRow
          delegate={delegate}
          code={code}
          onCodeChange={setCode}
          onConfirm={onConfirm}
          confirming={confirm.isPending}
          onRevoke={onRevoke}
          revoking={revoke.isPending}
        />
      ) : (
        <div className="space-y-3">
          <div>
            <Label htmlFor="delegate-name-input">Their name</Label>
            <Input
              id="delegate-name-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Tunde Adeyemi"
              disabled={authorize.isPending}
              data-testid="delegate-name"
            />
          </div>
          <div>
            <Label>Their WhatsApp number</Label>
            <PhoneInputWithCountry
              countryCode={countryCode}
              phone={phone}
              placeholder="0801 234 5678"
              disabled={authorize.isPending}
              data-testid="delegate-phone"
              onChange={(next) => {
                setCountryCode(next.countryCode);
                setDialCode(next.dialCode);
                setPhone(next.phone);
              }}
            />
          </div>
          <Button
            onClick={onAuthorize}
            disabled={!name.trim() || phone.length < 7 || authorize.isPending}
            data-testid="delegate-send"
          >
            {authorize.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <UserPlus className="mr-2 h-4 w-4" />
            )}
            Send them a code
          </Button>
        </div>
      )}
    </section>
  );
}

/**
 * The authorized delegate, in one of its two states.
 *
 * The unverified state is not a loading spinner — it can last as long as it takes the
 * buyer to reach the person and read the code back. Showing it plainly is what stops a
 * buyer nominating twice because nothing appeared to happen.
 */
function DelegateRow({
  delegate,
  code,
  onCodeChange,
  onConfirm,
  confirming,
  onRevoke,
  revoking,
}: {
  delegate: CaseDelegate;
  code: string;
  onCodeChange: (code: string) => void;
  onConfirm: () => void;
  confirming: boolean;
  onRevoke: () => void;
  revoking: boolean;
}) {
  const [confirmingRemoval, setConfirmingRemoval] = useState(false);

  return (
    <div className="space-y-4" data-testid="delegate-row">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-viridian-xlight text-brand-viridian">
          <ShieldCheck className="h-5 w-5" />
        </span>
        <div>
          <p className="font-medium text-foreground" data-testid="delegate-current-name">
            {delegate.name}
          </p>
          <p className="text-sm text-brand-on-surface-variant">
            {delegate.phoneE164}
            {" — "}
            {delegate.verified
              ? "receiving status updates"
              : "waiting for their code"}
          </p>
        </div>
      </div>

      {!delegate.verified && (
        <div className="space-y-2 border-t pt-4">
          <p className="text-sm text-brand-on-surface-variant">
            We sent a 6-digit code to that number on WhatsApp. Ask them to read it to you,
            then enter it here — they won&apos;t receive anything until you do.
          </p>
          <input
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            value={code}
            onChange={(e) => onCodeChange(e.target.value.replace(/\D/g, ""))}
            placeholder="654123"
            data-testid="delegate-code"
            className="flex h-10 w-40 rounded-md border border-input bg-background px-3 py-2 text-base outline-none focus:ring-2 focus:ring-ring md:text-sm"
          />
          <div>
            <Button
              onClick={onConfirm}
              disabled={code.length < 6 || confirming}
              data-testid="delegate-confirm"
            >
              {confirming && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Confirm delegate
            </Button>
          </div>
        </div>
      )}

      {confirmingRemoval ? (
        <div className="space-y-3 border-t pt-4">
          <p className="text-sm text-brand-on-surface-variant" data-testid="delegate-revoke-warning">
            {delegate.name} will stop receiving updates about this verification from the
            next one onwards. You can authorize someone else afterwards.
          </p>
          <div className="flex gap-2">
            <Button
              variant="destructive"
              onClick={onRevoke}
              disabled={revoking}
              data-testid="delegate-revoke-confirm"
            >
              {revoking && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Remove delegate
            </Button>
            <Button variant="ghost" onClick={() => setConfirmingRemoval(false)}>
              Keep them
            </Button>
          </div>
        </div>
      ) : (
        <div className="border-t pt-4">
          <Button
            variant="outline"
            onClick={() => setConfirmingRemoval(true)}
            data-testid="delegate-revoke"
          >
            Remove delegate
          </Button>
        </div>
      )}
    </div>
  );
}

/** Same join the linking form uses — the backend normalises, but it must arrive E.164. */
function toE164(dialCode: string, phone: string): string {
  return `${dialCode}${phone.replace(/\D/g, "").replace(/^0+/, "")}`;
}

"use client";

import { Checkbox } from "@3rdparty/ui/checkbox";
import { WhatsAppConsent } from "@/types/whatsappConsent";

/**
 * The two §7.4.6 opt-ins, as a pair of separate unticked controls.
 *
 * Three things about this component are requirements rather than styling choices:
 *
 * **They are two controls, not one.** Progress updates about a verification the customer
 * paid for and marketing about everything else are different asks; bundling them would
 * make the marketing consent unevidenced, and marketing consent is exactly what §7.10
 * counts as the channel's growth asset.
 *
 * **They start unticked, always.** The component holds no default of its own — it renders
 * what it is given, and the backend's "no record" state is both `false`. A pre-ticked box
 * is not consent.
 *
 * **It is presentational.** It lives in `shared/` because the same control renders on the
 * authenticated pay screen and on the public `/wa/pay/<token>` landing (D76), which write
 * through different endpoints — one session-authenticated, one grant-scoped. Each caller
 * owns its own submit; this owns the words and the markup, so the two surfaces cannot
 * drift into asking different questions.
 */
export default function WhatsAppOptInControls({
  consent,
  onChange,
  disabled = false,
}: {
  consent: WhatsAppConsent;
  onChange: (next: WhatsAppConsent) => void;
  disabled?: boolean;
}) {
  return (
    <div
      className="space-y-3 rounded-lg border border-border bg-brand-surface-low px-4 py-3"
      data-testid="wa-optin"
    >
      <p className="text-xs font-medium uppercase tracking-wide text-brand-on-surface-variant">
        WhatsApp updates
      </p>

      <label className="flex items-start gap-3">
        <Checkbox
          checked={consent.utility}
          disabled={disabled}
          onCheckedChange={(c) => onChange({ ...consent, utility: c === true })}
          data-testid="wa-optin-utility"
        />
        <span className="text-sm text-foreground">
          Send me progress updates about this verification on WhatsApp.
        </span>
      </label>

      <label className="flex items-start gap-3">
        <Checkbox
          checked={consent.marketing}
          disabled={disabled}
          onCheckedChange={(c) => onChange({ ...consent, marketing: c === true })}
          data-testid="wa-optin-marketing"
        />
        <span className="text-sm text-foreground">
          Send me occasional Veriprops news and offers on WhatsApp.
        </span>
      </label>

      <p className="text-xs text-brand-on-surface-variant">
        Either way, we&apos;ll email you everything important. You can change this any time in
        your account settings, or reply <strong>STOP</strong> on WhatsApp.
      </p>
    </div>
  );
}

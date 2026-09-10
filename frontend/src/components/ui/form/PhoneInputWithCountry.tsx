import CountryCodeSelect, { countries } from "./CountryCodeSelect";

interface PhoneInputWithCountryProps {
  /** ISO country code (e.g. "NG") — selects both the flag and the dial code. */
  countryCode: string;
  /** National number, digits only. */
  phone: string;
  /**
   * Receives the whole triple, because the dial code is derived here: a caller that
   * stored only the country would have to re-derive it, and the two could drift.
   */
  onChange: (next: { countryCode: string; dialCode: string; phone: string }) => void;
  /** The number has been OTP-verified: locked, and shown in the success colour. */
  isVerified?: boolean;
  /** Locked for any other reason (a request in flight, say) — no success styling. */
  disabled?: boolean;
  placeholder: string;
  "data-testid"?: string;
}

/**
 * Country selector + national-number input, controlled by value rather than bound to a
 * form. Used by the signup verification step, the OAuth profile-completion modal, and
 * WhatsApp account linking — three different form shapes, which is exactly why it takes
 * values instead of a `UseFormReturn`.
 */
const PhoneInputWithCountry = ({
  countryCode,
  phone,
  onChange,
  isVerified = false,
  disabled = false,
  placeholder,
  "data-testid": testId,
}: PhoneInputWithCountryProps) => {
  const selected = countries.find((c) => c.code === countryCode);
  const locked = isVerified || disabled;

  return (
    <div className="flex gap-1.5">
      <CountryCodeSelect
        value={countryCode}
        disabled={locked}
        onChange={(code) => {
          const country = countries.find((c) => c.code === code);
          onChange({ countryCode: code, dialCode: country?.dialCode ?? "", phone });
        }}
      />
      <div
        className={`flex flex-1 items-center rounded-md border bg-background ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 ${
          isVerified ? "border-[hsl(var(--success))]" : "border-input"
        } ${locked ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        <span className="pl-3 text-sm text-muted-foreground select-none shrink-0">
          {selected?.dialCode}
        </span>
        <input
          type="tel"
          name="phone"
          autoComplete="tel-national"
          placeholder={placeholder}
          disabled={locked}
          value={phone}
          data-testid={testId}
          onChange={(e) =>
            onChange({
              countryCode,
              dialCode: selected?.dialCode ?? "",
              phone: e.target.value.replace(/\D/g, ""),
            })
          }
          className="flex h-10 rounded-2xl w-full bg-transparent px-2 py-2 text-base outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed md:text-sm"
        />
      </div>
    </div>
  );
};

export default PhoneInputWithCountry;

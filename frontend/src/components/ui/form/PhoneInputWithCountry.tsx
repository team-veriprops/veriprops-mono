import CountryCodeSelect, { countries } from "./CountryCodeSelect";
import type { UseFormReturn } from "react-hook-form";
import { VerifyFormValues } from "../verified_input/VerifiedInput";

interface PhoneInputWithCountryProps {
  form: UseFormReturn<VerifyFormValues>;
  isVerified: boolean;
  onChanged: () => void;
  placeholder: string;
}

const PhoneInputWithCountry = ({ form, isVerified, onChanged, placeholder }: PhoneInputWithCountryProps) => {
  const countryCode = form.watch("countryCode");
  const selected = countries.find((c) => c.code === countryCode);

  return (
    <div className="flex gap-1.5">
      <CountryCodeSelect
        value={countryCode}
        disabled={isVerified}
        onChange={(code) => {
          const country = countries.find((c) => c.code === code);
          form.setValue("countryCode", code, { shouldValidate: true });
          form.setValue("dialCode", country?.dialCode ?? "", { shouldValidate: true });
          onChanged();
        }}
      />
      <div
        className={`flex flex-1 items-center rounded-md border bg-background ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 ${
          isVerified ? "border-[hsl(var(--success))]" : "border-input"
        } ${isVerified ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        <span className="pl-3 text-sm text-muted-foreground select-none shrink-0">
          {selected?.dialCode}
        </span>
        <input
          type="tel"
          name="phone"
          autoComplete="tel-national"
          placeholder={placeholder}
          disabled={isVerified}
          value={form.watch("phone")}
          onChange={(e) => {
            const stripped = e.target.value.replace(/\D/g, "");
            form.setValue("phone", stripped, { shouldValidate: true });
            onChanged();
          }}
          className="flex h-10 rounded-2xl w-full bg-transparent px-2 py-2 text-base outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed md:text-sm"
        />
      </div>
    </div>
  );
};

export default PhoneInputWithCountry;
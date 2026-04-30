"use client";

import Link from "next/link";
import { Checkbox } from "@3rdparty/ui/checkbox";
import { ConsentDocument } from "@components/website/auth/models";
interface ConsentCheckboxProps {
  doc: ConsentDocument;
  checked: boolean;
  onChange: (checked: boolean) => void;
  error?: string;
  id?: string;
}

export default function ConsentCheckbox({ doc, checked, onChange, error, id }: ConsentCheckboxProps) {
  const inputId = id ?? `consent-${doc.type}`;
  return (
    <div>
      <label
        htmlFor={inputId}
        className="flex items-start gap-3 cursor-pointer select-none"
      >
        <Checkbox
          id={inputId}
          checked={checked}
          onCheckedChange={(value) => onChange(value === true)}
          className="mt-0.5"
        />
        <span className="text-sm leading-relaxed" style={{ color: "var(--brand-on-surface)" }}>
          I have read and accept the{" "}
          <Link
            href={doc.href}
            target="_blank"
            rel="noopener"
            className="font-semibold underline-offset-2 hover:underline"
            style={{ color: "var(--brand-viridian)" }}
          >
            {doc.title}
          </Link>{" "}
          <span
            className="font-mono text-[11px]"
            style={{ color: "var(--brand-on-surface-variant)" }}
            aria-label={`version ${doc.consentVersion}`}
          >
            v{doc.consentVersion}
          </span>
        </span>
      </label>
      {error && (
        <p className="mt-1.5 ml-7 text-xs" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      )}
    </div>
  );
}

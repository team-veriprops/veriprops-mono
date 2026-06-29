import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle } from "lucide-react";

import { ConsentSignoffStatus, type LegalDocument as LegalDocumentModel } from "@app-types/models";

/**
 * Renders a backend-served legal document: title, version + effective date, a
 * draft banner for clauses still pending legal sign-off (§B), the Markdown body,
 * and the standing report-footer tagline. Content is owned by the backend
 * (single source of truth) so consent ties to the exact text shown.
 */
export default function LegalDocument({ doc }: { doc: LegalDocumentModel }) {
  const isDraft = doc.signoffStatus === ConsentSignoffStatus.DRAFT;
  const effective = doc.effectiveAt
    ? new Date(doc.effectiveAt).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : null;

  return (
    <article
      className="max-w-3xl mx-auto px-6 lg:px-8 py-16"
      data-testid="legal-document"
      data-legal-type={doc.type}
    >
      <header className="mb-8">
        <h1
          className="editorial-spacing text-3xl md:text-4xl font-bold mb-3"
          style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display)" }}
        >
          {doc.title}
        </h1>
        <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
          Version {doc.consentVersion}
          {effective ? ` · Effective ${effective}` : ""}
        </p>
      </header>

      {isDraft && (
        <div
          className="flex items-start gap-3 rounded-xl p-4 mb-10"
          role="note"
          data-testid="legal-draft-banner"
          style={{ backgroundColor: "var(--brand-gold-xlight)", color: "var(--brand-gold)" }}
        >
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" aria-hidden="true" />
          <p className="text-sm leading-relaxed">
            <strong>Draft — pending legal sign-off.</strong> This document reflects our
            intended terms. The exact wording is being finalised with counsel and may
            change before it becomes binding.
          </p>
        </div>
      )}

      <div className="space-y-1" style={{ color: "var(--brand-on-surface)" }}>
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
          {doc.body ?? ""}
        </ReactMarkdown>
      </div>

      <p
        className="mt-12 pt-6 text-xs italic"
        style={{ borderTop: "1px solid rgba(196,198,207,0.3)", color: "rgba(68,71,78,0.7)" }}
      >
        Veriprops — Jurisdiction: Nigeria. &ldquo;We reduce uncertainty. We do not
        eliminate it.&rdquo;
      </p>
    </article>
  );
}

// Map Markdown elements to brand-styled JSX (no typography plugin in the project).
const markdownComponents = {
  h2: (props: React.ComponentProps<"h2">) => (
    <h2
      className="editorial-spacing text-xl font-bold mt-10 mb-3"
      style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display)" }}
      {...props}
    />
  ),
  h3: (props: React.ComponentProps<"h3">) => (
    <h3 className="text-base font-semibold mt-6 mb-2" style={{ color: "var(--brand-navy)" }} {...props} />
  ),
  p: (props: React.ComponentProps<"p">) => (
    <p className="text-sm leading-relaxed mb-4" {...props} />
  ),
  ul: (props: React.ComponentProps<"ul">) => (
    <ul className="list-disc pl-5 space-y-2 mb-4 text-sm leading-relaxed" {...props} />
  ),
  ol: (props: React.ComponentProps<"ol">) => (
    <ol className="list-decimal pl-5 space-y-2 mb-4 text-sm leading-relaxed" {...props} />
  ),
  li: (props: React.ComponentProps<"li">) => <li {...props} />,
  strong: (props: React.ComponentProps<"strong">) => (
    <strong style={{ color: "var(--brand-navy)" }} {...props} />
  ),
  a: (props: React.ComponentProps<"a">) => (
    <a className="underline" style={{ color: "var(--brand-viridian)" }} {...props} />
  ),
  table: (props: React.ComponentProps<"table">) => (
    <div className="overflow-x-auto mb-4">
      <table className="w-full text-sm border-collapse" {...props} />
    </div>
  ),
  th: (props: React.ComponentProps<"th">) => (
    <th
      className="text-left font-semibold p-2 align-top"
      style={{ backgroundColor: "var(--brand-surface-high)", color: "var(--brand-navy)" }}
      {...props}
    />
  ),
  td: (props: React.ComponentProps<"td">) => (
    <td className="p-2 align-top" style={{ borderTop: "1px solid rgba(196,198,207,0.3)" }} {...props} />
  ),
};

"use client";

interface AuthHeadingProps {
  eyebrow?: string;
  title: string;
  subtitle?: React.ReactNode;
}

export default function AuthHeading({ eyebrow, title, subtitle }: AuthHeadingProps) {
  return (
    <div className="mb-8">
      {eyebrow && (
        <span
          className="inline-block text-xs font-semibold uppercase tracking-widest mb-3"
          style={{ color: "var(--brand-viridian)" }}
        >
          {eyebrow}
        </span>
      )}
      <h1
        className="text-3xl sm:text-4xl font-extrabold font-display editorial-spacing leading-[1.1]"
        style={{ color: "var(--brand-navy)" }}
      >
        {title}
      </h1>
      {subtitle && (
        <p
          className="mt-3 text-sm sm:text-base leading-relaxed"
          style={{ color: "var(--brand-on-surface-variant)" }}
        >
          {subtitle}
        </p>
      )}
    </div>
  );
}

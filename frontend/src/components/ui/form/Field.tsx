"use client";

import { useId } from "react";

/**
 * A labelled form row, shared by the signup steps and the OAuth profile-completion modal.
 *
 * The control receives the id the label points at, rather than being wrapped and hoping for
 * the best: a label that only *looks* attached is invisible to assistive tech. An unbound
 * `<select>` has no accessible name at all (axe `select-name`, critical), and an unbound
 * `<input>` falls back to its placeholder, which disappears the moment the user types.
 */
interface FieldProps {
  label: string;
  error?: string;
  /** Receives the id the control must carry, so the binding cannot be forgotten. */
  children: (id: string) => React.ReactNode;
}

export function Field({ label, error, children }: FieldProps) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="text-sm font-semibold text-brand-navy">
        {label}
      </label>
      {children(id)}
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}

/**
 * The same row for several controls that share one label — a row of choice buttons, say.
 * There is no single control for `htmlFor` to point at, so the group carries the name.
 */
interface FieldGroupProps {
  label: string;
  error?: string;
  /** Applied to the group itself, so callers keep their own layout without an extra wrapper. */
  className?: string;
  children: React.ReactNode;
}

export function FieldGroup({ label, error, className, children }: FieldGroupProps) {
  const labelId = useId();
  return (
    <div className="space-y-1.5">
      <span id={labelId} className="text-sm font-semibold text-brand-navy">
        {label}
      </span>
      <div role="group" aria-labelledby={labelId} className={className}>
        {children}
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}

"use client";

import { ReactNode } from "react";
import { X } from "lucide-react";
import Stepper from "@components/website/auth/signup/Stepper";
import { Button } from "@3rdparty/ui/button";
import { useBodyOverflowHidden } from "@hooks/useBodyOverflowHidden";
import BrandLogo from "@components/ui/BrandLogo";

interface WizardOverlayProps {
  /** Step titles for the progress indicator. */
  steps: string[];
  /** 0-based active step. */
  current: number;
  /** Called by the close (✕) control — typically routes back to the owning surface. */
  onClose: () => void;
  title?: string;
  children: ReactNode;
  /** Sticky footer (Back / Continue controls). */
  footer?: ReactNode;
  /** data-testid prefix, e.g. "agent-apply" → "agent-apply-overlay". */
  testIdPrefix: string;
  /** Hides the close (✕) control for a compulsory, non-dismissible flow. Default true. */
  closable?: boolean;
}

/**
 * Route-backed full-screen wizard shell (PRD Phases 3/5). Renders a fixed layer
 * above the AppShell chrome so the flow "covers everywhere" while the route stays
 * deep-linkable, back-button-safe and refresh-resumable. Reused by agent
 * onboarding, property submission, and payment.
 */
export default function WizardOverlay({
  steps,
  current,
  onClose,
  title,
  children,
  footer,
  testIdPrefix,
  closable = true,
}: WizardOverlayProps) {
  useBodyOverflowHidden(true);

  return (
    <div
      className="fixed inset-0 z-[70] flex flex-col bg-background"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      data-testid={`${testIdPrefix}-overlay`}
    >
      {/* Header: brand + stepper + close */}
      <header className="shrink-0 border-b border-border bg-card/95 backdrop-blur-sm">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <BrandLogo />
          {closable && (
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              aria-label="Close"
              data-testid={`${testIdPrefix}-close`}
            >
              <X className="h-5 w-5" />
            </Button>
          )}
        </div>
        <div className="mx-auto w-full max-w-3xl px-4 pb-4 sm:px-6">
          <Stepper steps={steps} current={current} />
        </div>
      </header>

      {/* Body */}
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
          {title && <h1 className="mb-6 text-2xl font-bold text-foreground">{title}</h1>}
          {children}
        </div>
      </main>

      {/* Sticky footer */}
      {footer && (
        <footer className="shrink-0 border-t border-border bg-card/95 backdrop-blur-sm">
          <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
            {footer}
          </div>
        </footer>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@3rdparty/ui/dialog";
import { useAgentApplication } from "../libs/useAgentApplicationQueries";
import AgentOnboardingContainer from "./AgentOnboardingContainer";

export default function OnboardingGateModal() {
  const { data: application, isLoading } = useAgentApplication();
  const [dismissed, setDismissed] = useState(false);

  if (isLoading || !application || application.status === "APPROVED") return null;

  const isDraft = application.status === "DRAFT";
  const open = isDraft || !dismissed;

  return (
    <Dialog
      open={open}
      onOpenChange={isDraft ? undefined : () => setDismissed(true)}
    >
      <DialogContent
        className="sm:max-w-2xl overflow-y-auto max-h-[90vh]"
        showCloseButton={!isDraft}
        onInteractOutside={isDraft ? (e) => e.preventDefault() : undefined}
        onEscapeKeyDown={isDraft ? (e) => e.preventDefault() : undefined}
      >
        <DialogHeader>
          <DialogTitle style={{ color: "var(--brand-navy)" }}>
            Agent Onboarding
          </DialogTitle>
        </DialogHeader>
        <AgentOnboardingContainer compact />
      </DialogContent>
    </Dialog>
  );
}

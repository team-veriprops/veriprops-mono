"use client";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@3rdparty/ui/alert-dialog";
import { buttonVariants } from "@3rdparty/ui/button";
import type { ReactNode } from "react";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  /** A destructive action (money moves, work stops) gets the destructive button. */
  destructive?: boolean;
  pending?: boolean;
  /** Keeps the confirm button disabled — e.g. until a required reason is filled in. */
  confirmDisabled?: boolean;
  testId?: string;
  /** Extra content between the description and the buttons, such as a reason field. */
  children?: ReactNode;
}

/**
 * An explicit yes/no before an action that cannot be taken back. Built on the alert dialog, so
 * it traps focus and cannot be dismissed by clicking outside: the person has to choose.
 *
 * Confirming does not close it — the caller does, once the action has succeeded — so a refused
 * request leaves the dialog, and anything typed into it, in place.
 */
export function ConfirmDialog({
  open, onOpenChange, title, description, confirmLabel, onConfirm, destructive, pending, confirmDisabled,
  testId, children,
}: ConfirmDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent data-testid={testId}>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        {children}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending} data-testid={testId && `${testId}-back`}>Go back</AlertDialogCancel>
          <AlertDialogAction
            onClick={(event) => {
              event.preventDefault(); // Radix would close it here, before the action settles.
              onConfirm();
            }}
            disabled={pending || confirmDisabled}
            className={destructive ? buttonVariants({ variant: "destructive" }) : undefined}
            data-testid={testId && `${testId}-confirm`}
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

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
  testId?: string;
}

/**
 * An explicit yes/no before an action that cannot be taken back. Built on the alert dialog, so
 * it traps focus and cannot be dismissed by clicking outside: the person has to choose.
 */
export function ConfirmDialog({
  open, onOpenChange, title, description, confirmLabel, onConfirm, destructive, pending, testId,
}: ConfirmDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent data-testid={testId}>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending} data-testid={testId && `${testId}-back`}>Go back</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={pending}
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

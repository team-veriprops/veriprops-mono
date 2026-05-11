"use client";

import { AlertTriangle } from "lucide-react";

interface Props {
  openCount: number;
}

export default function ConflictBadge({ openCount }: Props) {
  if (openCount === 0) return null;
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-xs font-semibold">
      <AlertTriangle className="h-3 w-3" />
      {openCount} conflict{openCount !== 1 ? "s" : ""}
    </span>
  );
}

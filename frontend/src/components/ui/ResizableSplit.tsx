"use client";

import { ReactNode, useRef, useState } from "react";
import { GripVertical } from "lucide-react";
import { cn } from "@lib/utils";

/** The narrowest either side may be dragged to, as a percentage of the width. */
export const SPLIT_MIN_PERCENT = 15;
/** How far one arrow-key press moves the divider. */
export const SPLIT_KEY_STEP = 5;
const CENTRE = 50;

/** Keep the left side's share of the width where both sides stay usable. */
export function clampSplit(percent: number, min = SPLIT_MIN_PERCENT): number {
  return Math.min(100 - min, Math.max(min, percent));
}

/** The left side's share of the width when the pointer is at `clientX` over `bounds`. */
export function splitAt(clientX: number, bounds: { left: number; width: number }): number {
  return clampSplit(bounds.width > 0 ? ((clientX - bounds.left) / bounds.width) * 100 : CENTRE);
}

interface Props {
  left: ReactNode;
  right: ReactNode;
  /** Names the divider for screen readers, e.g. "Resize selfie and passport". */
  label: string;
  className?: string;
  testId?: string;
}

/**
 * Two panes side by side with a divider dragged from the centre to give either one more room.
 * The divider follows a mouse, finger or pen (pointer capture keeps it while dragging), and
 * as a keyboard control moves with the arrow keys; Home/End go to the limits and a double
 * click (or Enter) puts it back in the centre.
 */
export function ResizableSplit({ left, right, label, className, testId }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [percent, setPercent] = useState(CENTRE);
  const [dragging, setDragging] = useState(false);

  const follow = (clientX: number) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (rect) setPercent(splitAt(clientX, rect));
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    const moves: Record<string, number> = {
      ArrowLeft: percent - SPLIT_KEY_STEP,
      ArrowRight: percent + SPLIT_KEY_STEP,
      Home: SPLIT_MIN_PERCENT,
      End: 100 - SPLIT_MIN_PERCENT,
      Enter: CENTRE,
    };
    if (e.key in moves) {
      e.preventDefault();
      setPercent(clampSplit(moves[e.key]));
    }
  };

  return (
    <div ref={containerRef} data-testid={testId}
      className={cn("relative flex w-full overflow-hidden rounded-lg border", dragging && "select-none", className)}>
      <div className="min-w-0 overflow-hidden" style={{ width: `${percent}%` }} data-testid={testId && `${testId}-left`}>
        {left}
      </div>
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label={label}
        aria-valuemin={SPLIT_MIN_PERCENT}
        aria-valuemax={100 - SPLIT_MIN_PERCENT}
        aria-valuenow={Math.round(percent)}
        tabIndex={0}
        onKeyDown={onKeyDown}
        onDoubleClick={() => setPercent(CENTRE)}
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId);
          setDragging(true);
        }}
        onPointerMove={(e) => dragging && follow(e.clientX)}
        onPointerUp={(e) => {
          e.currentTarget.releasePointerCapture(e.pointerId);
          setDragging(false);
        }}
        data-testid={testId && `${testId}-divider`}
        className="group relative flex w-3 shrink-0 cursor-col-resize touch-none items-center justify-center bg-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="flex h-10 w-4 items-center justify-center rounded border bg-background shadow-sm group-hover:bg-muted">
          <GripVertical className="size-3.5 text-muted-foreground" aria-hidden />
        </span>
      </div>
      <div className="min-w-0 flex-1 overflow-hidden" data-testid={testId && `${testId}-right`}>
        {right}
      </div>
    </div>
  );
}

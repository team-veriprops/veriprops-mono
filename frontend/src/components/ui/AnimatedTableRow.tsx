"use client";

import { motion } from "framer-motion";
import { ReactNode } from "react";

interface AnimatedTableRowProps {
  id: string;
  index: number;
  elementOfInterest?: string | null;
  children: ReactNode;
  isClickable?: boolean;
  onClick?: () => void
  /** Automation anchor for the row; the row's own id is always exposed as `data-row-id`. */
  testId?: string;
}

export function AnimatedTableRow({
  id,
  index,
  elementOfInterest,
  children,
  isClickable,
  onClick,
  testId,
}: AnimatedTableRowProps) {
  return (
    <motion.tr
      key={id}
      data-testid={testId}
      data-row-id={id}
      initial={{ opacity: 0, y: 20 }}
      animate={{
        opacity: elementOfInterest === id ? 0.5 : 1,
        y: 0,
        scale: elementOfInterest === id ? 0.95 : 1,
      }}
      transition={{ delay: index * 0.05 }}
      onClick={onClick}
      className={`hover:bg-muted/30 transition-colors ${isClickable?? false ? "cursor-pointer" : ""}`}
    >
      {children}
    </motion.tr>
  );
}

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@components/3rdparty/ui/tooltip";
import { memo, ReactNode } from "react";

interface ToolTipComponentProps {
  label: string;
  children: ReactNode;
  /** Which side of the trigger the tooltip appears on (default "top"). */
  side?: "top" | "right" | "bottom" | "left";
}

function ToolTipComponent({
  label,
  children,
  side = "top",
}: ToolTipComponentProps) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>{children}</TooltipTrigger>
        <TooltipContent side={side}>
          <p className="text-xs">{label}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export default memo(ToolTipComponent)

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
}

function ToolTipComponent({
  label,
  children,
}: ToolTipComponentProps) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>{children}</TooltipTrigger>
        <TooltipContent>
          <p className="text-xs">{label}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export default memo(ToolTipComponent)

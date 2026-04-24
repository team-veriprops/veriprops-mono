import { Button } from "@components/3rdparty/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@components/3rdparty/ui/tooltip";

export default function TrustPerformanceScoreComponent({trustScore}: {trustScore: number}) {
  const radius = 50;
  const circumference = 2 * Math.PI * radius;
  const progress = (trustScore / 100) * circumference;
  return (
    <div className="flex items-center gap-4">
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className="relative"
            role="img"
            aria-label={`Trust score: ${trustScore} out of 100`}
          >
            <svg className="transform -rotate-90" width="120" height="120">
              <circle
                cx="60"
                cy="60"
                r={radius}
                stroke="#DFF6F0"
                strokeWidth="8"
                fill="none"
                // strokeDasharray={circumference}
                // strokeDashoffset={circumference - progress}
                // strokeLinecap="round"
                // className="transition-all duration-500"
              />
              <circle
                cx="60"
                cy="60"
                r={radius}
                stroke="var(--color-success)"
                strokeWidth="8"
                fill="none"
                strokeDasharray={circumference}
                strokeDashoffset={circumference - progress}
                strokeLinecap="round"
                className="transition-all duration-500"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <div className="text-3xl font-bold text-foreground">
                {trustScore}
              </div>
              <div className="text-xs text-muted-foreground">TPS</div>
            </div>
          </div>
        </TooltipTrigger>
        <TooltipContent side="left" className="max-w-xs ">
          <p className="font-semibold mb-2">Trust Performance Score (TPS)</p>
          <p className="text-sm">
            Your TPS is calculated from verified transactions, referrals,
            dispute history, and account longevity.
          </p>
          <Button
            variant="ghost"
            size="sm"
            className="mt-2 p-0 h-auto"
            // onClick={onViewDetails}
          >
            View details
          </Button>
        </TooltipContent>
      </Tooltip>
    </div>
  );
}

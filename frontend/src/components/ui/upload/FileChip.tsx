import { CheckCircle2, Loader2, AlertCircle, X } from 'lucide-react';
import { Badge } from '@3rdparty/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@3rdparty/ui/tooltip';
import { cn } from '@lib/utils';
import { UploadStatus } from './MediaCard';

interface FileChipProps {
  filename: string;
  status: UploadStatus;
  onRemove: () => void;
}

export function FileChip({ filename, status, onRemove }: FileChipProps) {
  const isPdf = filename.toLowerCase().endsWith('.pdf');
  const isVideo = filename.match(/\.(mp4|mov|webm|avi|m4v)$/i);
  
  const getStatusConfig = () => {
    switch (status) {
      case 'done':
        return {
          icon: CheckCircle2,
          bg: 'bg-success/10',
          text: 'text-success',
          border: 'border-success/20',
          label: 'Uploaded successfully',
        };
      case 'error':
        return {
          icon: AlertCircle,
          bg: 'bg-destructive/10',
          text: 'text-destructive',
          border: 'border-destructive/20',
          label: 'Upload failed',
        };
      default: // idle, compressing, uploading
        return {
          icon: Loader2,
          bg: 'bg-amber-50 dark:bg-amber-950',
          text: 'text-amber-700 dark:text-amber-400',
          border: 'border-amber-200 dark:border-amber-800',
          label: 'Uploading...',
          animate: true,
        };
    }
  };

  const config = getStatusConfig();
  const Icon = config.icon;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border text-sm transition-all',
              'px-3 py-2 sm:px-3 sm:py-1.5',
              config.bg,
              config.text,
              config.border
            )}
            role="status"
            aria-label={`${filename} - ${config.label}`}
          >
            <Icon
              className={cn(
                'h-3.5 w-3.5 sm:h-3 sm:w-3 shrink-0',
                config.animate && 'animate-spin'
              )}
            />
            <span className="truncate max-w-[100px] sm:max-w-[120px] text-xs sm:text-sm font-medium">
              {filename}
            </span>
            {isPdf && (
              <Badge variant="outline" className="text-[10px] px-1 py-0 h-4">
                PDF
              </Badge>
            )}
            {isVideo && (
              <Badge variant="secondary" className="text-[10px] px-1 py-0 h-4">
                VIDEO
              </Badge>
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onRemove();
              }}
              className={cn(
                'ml-1 shrink-0 rounded-full hover:bg-black/10 dark:hover:bg-white/10 transition-colors',
                'p-1 sm:p-0.5',
                'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1'
              )}
              aria-label={`Remove ${filename}`}
            >
              <X className="h-3.5 w-3.5 sm:h-3 sm:w-3" />
            </button>
          </div>
        </TooltipTrigger>
        <TooltipContent className="hidden sm:block">
          <p className="font-medium">{filename}</p>
          <p className="text-xs text-muted-foreground">{config.label}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

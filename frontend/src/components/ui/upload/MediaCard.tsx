import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Image as ImageIcon,
  Loader2,
  XCircle,
  FileText,
  Play,
  Video,
} from "lucide-react";
import * as pdfjsLib from "pdfjs-dist";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { Textarea } from "@3rdparty/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@3rdparty/ui/select";
import { Badge } from "@3rdparty/ui/badge";
import { cn } from "@lib/utils";

export type UploadStatus =
  | "idle"
  | "compressing"
  | "uploading"
  | "done"
  | "error";

// export const MEDIA_TYPES = [
//   "Property Photo",
//   "Property Video",
//   "Survey Plan",
//   "C of O",
//   "Deed",
//   "Receipt",
//   "Building Permit",
//   "Floor Plan",
//   "Virtual Tour",
//   "Walkthrough Video",
//   "Drone Footage",
//   "Other",
// ] as const;

// export type MediaType = (typeof MEDIA_TYPES)[number];


export interface MediaType {
  key: string;
  type: "image" | "video" | "pdf"
  title: string;
}

export interface MediaMetadata {
  type: MediaType | null;
  title: string;
  description: string;
  url?: string;
}

export interface MediaItem {
  id: string;
  file?: File;
  preview: string;
  filename: string;
  size: number;
  status: UploadStatus;
  progress: number;
  error?: string;
  uploadedUrl?: string;
  metadata: MediaMetadata;
  estimatedTimeRemaining?: number;
  uploadSpeed?: number;
}

interface MediaCardProps {
  media: MediaItem;
  onDelete: (id: string) => void;
  onRetry: (id: string) => void;
  onCancel: (id: string) => void;
  onMetadataChange: (id: string, metadata: Partial<MediaMetadata>) => void;
  requiredTypes?: MediaType[];
  allPossibleTypes?: MediaType[];
  "aria-label"?: string;
}

export function MediaCard({
  media,
  onDelete,
  onRetry,
  onCancel,
  onMetadataChange,
  requiredTypes = [],
  allPossibleTypes = [],
  "aria-label": ariaLabel,
}: MediaCardProps) {
  const [titleError, setTitleError] = useState("");
  const [typeError, setTypeError] = useState("");
  const [pdfThumbnail, setPdfThumbnail] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState(false);
  const [videoThumbnail, setVideoThumbnail] = useState<string | null>(null);
  const [videoDuration, setVideoDuration] = useState<number | null>(null);
  const [videoError, setVideoError] = useState(false);

  allPossibleTypes = allPossibleTypes.length > 0 ? allPossibleTypes : requiredTypes;

  // Detect if file is PDF or video
  const isPdf =
    media.filename.toLowerCase().endsWith(".pdf") ||
    media.file?.type === "application/pdf";
  const isVideo =
    media.filename.match(/\.(mp4|mov|webm|avi|m4v)$/i) ||
    media.file?.type.startsWith("video/");

  // Generate PDF thumbnail
  useEffect(() => {
    if (isPdf && media.file) {
      const generatePdfThumbnail = async () => {
        try {
          pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
            "pdfjs-dist/build/pdf.worker.min.mjs",
            import.meta.url
          ).toString();

          // Load PDF
          const arrayBuffer = await media?.file?.arrayBuffer();
          const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
          const page = await pdf.getPage(1);

          // Render to canvas
          const viewport = page.getViewport({ scale: 0.5 });
          const canvas = document.createElement("canvas");
          canvas.width = viewport.width;
          canvas.height = viewport.height;

          const context = canvas.getContext("2d");
          if (!context) {
            setPdfError(true);
            return;
          }

          await page.render({
            canvasContext: context,
            viewport,
            canvas,
          }).promise;

          setPdfThumbnail(canvas.toDataURL());
        } catch (error) {
          console.error("PDF thumbnail generation failed:", error);
          setPdfError(true);
        }
      };

      generatePdfThumbnail();
    }
  }, [isPdf, media.file]);

  // Generate video thumbnail and extract duration
  useEffect(() => {
    if (isVideo && media.file) {
      const generateVideoThumbnail = async () => {
        try {
          const videoUrl = URL.createObjectURL(media?.file!);
          const video = document.createElement("video");
          video.preload = "metadata";
          video.muted = true;
          video.playsInline = true;

          video.onloadedmetadata = () => {
            setVideoDuration(video.duration);
            const seekTime = Math.min(1, video.duration * 0.1);
            video.currentTime = seekTime;
          };

          video.onseeked = () => {
            try {
              const canvas = document.createElement("canvas");
              canvas.width = video.videoWidth;
              canvas.height = video.videoHeight;
              const ctx = canvas.getContext("2d");

              if (!ctx) {
                setVideoError(true);
                URL.revokeObjectURL(videoUrl);
                return;
              }

              ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
              setVideoThumbnail(canvas.toDataURL("image/jpeg", 0.8));
              URL.revokeObjectURL(videoUrl);
            } catch (error) {
              console.error("Video thumbnail generation failed:", error);
              setVideoError(true);
              URL.revokeObjectURL(videoUrl);
            }
          };

          video.onerror = () => {
            console.error("Video loading failed");
            setVideoError(true);
            URL.revokeObjectURL(videoUrl);
          };

          video.src = videoUrl;
        } catch (error) {
          console.error("Video processing failed:", error);
          setVideoError(true);
        }
      };

      generateVideoThumbnail();
    }
  }, [isVideo, media.file]);

const findMediaType = (key: string) =>
  allPossibleTypes.find((type: MediaType) => type.key === key);

  const validateTitle = (value: string) => {
    if (!value.trim()) {
      setTitleError("Title is required");
      return false;
    }
    if (value.trim().length < 3) {
      setTitleError("Title must be at least 3 characters");
      return false;
    }
    if (value.length > 120) {
      setTitleError("Title must be less than 120 characters");
      return false;
    }
    setTitleError("");
    return true;
  };

  const validateType = (value: string) => {
    if (!value) {
      setTypeError("Type is required");
      return false;
    }
    setTypeError("");
    return true;
  };

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const formatTimeEstimate = (seconds: number): string => {
    if (seconds < 60) return `${Math.ceil(seconds)}s`;
    if (seconds < 3600) return `${Math.ceil(seconds / 60)}m`;
    return `${Math.ceil(seconds / 3600)}h`;
  };

  useEffect(() => {
    if (media.metadata.title) validateTitle(media.metadata.title);
    if (media.metadata.type) validateType(media.metadata.type.key);
  }, [media.metadata.title, media.metadata.type]);

  const statusConfig = {
    idle: { icon: ImageIcon, color: "text-muted-foreground", label: "Ready" },
    compressing: {
      icon: Loader2,
      color: "text-warning",
      label: "Compressing...",
    },
    uploading: { icon: Loader2, color: "text-primary", label: "Uploading..." },
    done: { icon: CheckCircle2, color: "text-success", label: "Uploaded" },
    error: { icon: AlertCircle, color: "text-destructive", label: "Failed" },
  };

  const config = statusConfig[media.status];
  const Icon = config.icon;
  const isProcessing =
    media.status === "compressing" || media.status === "uploading";
  const isDone = media.status === "done";
  const hasError = media.status === "error";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95, y: 20 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95, y: -20 }}
      className={cn(
        "relative rounded-xl border bg-card shadow-sm overflow-hidden",
        "transition-all duration-200",
        hasError && "border-destructive/50 bg-destructive-light/20",
        isDone && "border-success/50"
      )}
      aria-label={ariaLabel}
    >
      {/* Image/PDF/Video preview */}
      <div className="relative aspect-video bg-muted overflow-hidden">
        {isVideo && videoThumbnail ? (
          <div className="relative w-full h-full">
            <img
              src={videoThumbnail}
              alt={media.metadata.title || media.filename}
              className="w-full h-full object-cover"
              loading="lazy"
            />
            <div className="absolute inset-0 flex items-center justify-center bg-black/30">
              <div className="bg-white/90 rounded-full p-3 sm:p-4">
                <Play
                  className="h-8 w-8 sm:h-12 sm:w-12 text-black"
                  fill="black"
                />
              </div>
            </div>
            {videoDuration && (
              <Badge
                variant="secondary"
                className="absolute bottom-2 right-2 bg-black/70 text-white text-xs px-2 py-1"
              >
                {formatDuration(videoDuration)}
              </Badge>
            )}
          </div>
        ) : isVideo ? (
          <div className="w-full h-full flex flex-col items-center justify-center bg-muted">
            <Video className="h-12 w-12 sm:h-16 sm:w-16 text-muted-foreground mb-2" />
            <p className="text-sm font-medium text-muted-foreground px-2 text-center">
              {media.filename}
            </p>
            <p className="text-xs text-muted-foreground">Video File</p>
            {videoDuration && (
              <Badge variant="outline" className="mt-2">
                {formatDuration(videoDuration)}
              </Badge>
            )}
          </div>
        ) : isPdf && pdfThumbnail && !pdfError ? (
          <div className="relative w-full h-full">
            <img
              src={pdfThumbnail}
              alt={media.metadata.title || media.filename}
              className="w-full h-full object-cover"
              loading="lazy"
            />
            <Badge
              variant="secondary"
              className="absolute top-2 right-2 bg-black/70 text-white"
            >
              PDF
            </Badge>
          </div>
        ) : isPdf ? (
          <div className="w-full h-full flex flex-col items-center justify-center bg-muted gap-3">
            <FileText className="h-16 w-16 text-muted-foreground" />
            <div className="text-center px-4">
              <p className="text-sm font-medium text-foreground truncate max-w-[200px]">
                {media.filename}
              </p>
              <p className="text-xs text-muted-foreground mt-1">PDF Document</p>
            </div>
          </div>
        ) : (
          <img
            src={media.preview}
            alt={media.metadata.title || media.filename}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        )}

        {/* Status overlay */}
        <AnimatePresence>
          {(isProcessing || hasError) && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center"
            >
              <div className="text-center">
                <Icon
                  className={cn("h-8 w-8 mx-auto mb-2", config.color, {
                    "animate-spin": isProcessing,
                  })}
                />
                <p className="text-sm font-medium">{config.label}</p>
                {media.progress > 0 && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {media.progress}%
                  </p>
                )}
                {media.status === "uploading" &&
                  media.uploadSpeed &&
                  media.estimatedTimeRemaining &&
                  media.estimatedTimeRemaining > 1 && (
                    <p className="text-xs text-muted-foreground mt-1">
                      {formatTimeEstimate(media.estimatedTimeRemaining)}{" "}
                      remaining
                      <span className="ml-2">
                        ({(media.uploadSpeed / 1024 / 1024).toFixed(1)} MB/s)
                      </span>
                    </p>
                  )}
                {isProcessing && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onCancel(media.id)}
                    className="mt-3"
                    aria-label="Cancel upload"
                  >
                    <XCircle className="h-3.5 w-3.5 mr-1.5" />
                    Cancel
                  </Button>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Delete button */}
        <Button
          size="icon"
          variant="destructive"
          onClick={() => onDelete(media.id)}
          className="absolute top-2 right-2 h-8 w-8 shadow-md"
          aria-label={`Delete ${media.filename}`}
        >
          <X className="h-4 w-4" />
        </Button>

        {/* Done indicator */}
        {isDone && (
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="absolute top-2 left-2 bg-success text-success-foreground rounded-full p-1.5"
          >
            <CheckCircle2 className="h-4 w-4" />
          </motion.div>
        )}
      </div>

      {/* Progress bar */}
      {isProcessing && (
        <div className="relative h-1 bg-progress-bg overflow-hidden">
          <motion.div
            className={cn(
              "absolute inset-y-0 left-0",
              media.status === "compressing"
                ? "bg-progress-compressing"
                : "bg-progress-uploading"
            )}
            initial={{ width: 0 }}
            animate={{ width: `${media.progress}%` }}
            transition={{ duration: 0.3 }}
          />
          {media.status === "compressing" && (
            <motion.div
              className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
              animate={{ x: ["-100%", "200%"] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
            />
          )}
        </div>
      )}

      {/* Metadata form */}
      <div className="p-4 space-y-3">
        {/* File info */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {isVideo ? (
            <Video className="h-3.5 w-3.5" />
          ) : isPdf ? (
            <FileText className="h-3.5 w-3.5" />
          ) : (
            <ImageIcon className="h-3.5 w-3.5" />
          )}
          <span className="truncate flex-1">{media.filename}</span>
          {isPdf && (
            <Badge variant="outline" className="text-xs">
              PDF
            </Badge>
          )}
          {isVideo && (
            <>
              <Badge variant="secondary" className="text-xs">
                VIDEO
              </Badge>
              {videoDuration && <span>{formatDuration(videoDuration)}</span>}
            </>
          )}
          <span>{(media.size / 1024).toFixed(0)}KB</span>
        </div>

        {/* Large video warning */}
        {isVideo && media.size > 50 * 1024 * 1024 && (
          <div className="p-3 bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-md">
            <div className="flex items-start gap-2">
              <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
              <div className="text-xs text-amber-800 dark:text-amber-200">
                <p className="font-medium">
                  Large video file ({(media.size / 1024 / 1024).toFixed(1)}MB)
                </p>
                <p className="mt-1">
                  Upload may take several minutes depending on your connection
                  speed.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Error message */}
        {hasError && media.error && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            className="flex items-start gap-2 p-3 rounded-lg bg-destructive-light text-destructive text-sm"
            role="alert"
          >
            <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="font-medium">Upload failed</p>
              <p className="text-xs mt-1">{media.error}</p>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onRetry(media.id)}
              className="flex-shrink-0"
              aria-label="Retry upload"
            >
              <RefreshCw className="h-3.5 w-3.5 mr-1" />
              Retry
            </Button>
          </motion.div>
        )}

        {/* Type select */}
        <div className="space-y-1.5">
          <Label htmlFor={`type-${media.id}`} className="text-xs">
            Type <span className="text-destructive">*</span>
          </Label>
          <Select
            value={media.metadata?.type?.key!}
            onValueChange={(value: string) => {
              onMetadataChange(media.id, { type: findMediaType(value) });
              validateType(value);
            }}
          >
            <SelectTrigger
              id={`type-${media.id}`}
              className={cn("h-9", typeError && "border-destructive")}
              aria-describedby={
                typeError ? `type-error-${media.id}` : undefined
              }
            >
              <SelectValue placeholder="Select document type" />
            </SelectTrigger>
            <SelectContent className="bg-popover">
              {allPossibleTypes.map((type) => {
                const isRequired = requiredTypes.includes(type);
                return (
                  <SelectItem key={type.key} value={type.key}>
                    <span className="flex items-center gap-2">
                      {type.title}
                      {isRequired && (
                        <Badge variant="destructive" className="text-xs">
                          Required
                        </Badge>
                      )}
                    </span>
                  </SelectItem>
                );
              })}
            </SelectContent>
          </Select>
          {typeError && (
            <p
              id={`type-error-${media.id}`}
              className="text-xs text-destructive"
              role="alert"
            >
              {typeError}
            </p>
          )}
        </div>

        {/* Title input */}
        <div className="space-y-1.5">
          <Label htmlFor={`title-${media.id}`} className="text-xs">
            Title <span className="text-destructive">*</span>
          </Label>
          <Input
            id={`title-${media.id}`}
            value={media.metadata.title}
            onChange={(e) => {
              const value = e.target.value;
              onMetadataChange(media.id, { title: value });
              validateTitle(value);
            }}
            onBlur={(e) => validateTitle(e.target.value)}
            placeholder="e.g., Front elevation view"
            maxLength={120}
            className={cn("h-9", titleError && "border-destructive")}
            aria-describedby={
              titleError ? `title-error-${media.id}` : undefined
            }
          />
          {titleError && (
            <p
              id={`title-error-${media.id}`}
              className="text-xs text-destructive"
              role="alert"
            >
              {titleError}
            </p>
          )}
        </div>

        {/* Description textarea */}
        <div className="space-y-1.5">
          <Label htmlFor={`description-${media.id}`} className="text-xs">
            Description{" "}
            <span className="text-muted-foreground">(optional)</span>
          </Label>
          <Textarea
            id={`description-${media.id}`}
            value={media.metadata.description}
            onChange={(e) =>
              onMetadataChange(media.id, { description: e.target.value })
            }
            placeholder="Add any additional details..."
            maxLength={1000}
            rows={2}
            className="text-sm resize-none"
          />
          <p className="text-xs text-muted-foreground text-right">
            {media.metadata.description.length}/1000
          </p>
        </div>
      </div>
    </motion.div>
  );
}

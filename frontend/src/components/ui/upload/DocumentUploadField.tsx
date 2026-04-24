import { useState, useCallback } from "react";
import { Upload, Loader2, AlertCircle } from "lucide-react";
import { Control, FieldValues, Path } from "react-hook-form";
import {
  FormField,
  FormItem,
  FormLabel,
  FormControl,
  FormDescription,
  FormMessage,
} from "@3rdparty/ui/form";
import { cn } from "@lib/utils";
import { FileChip } from "./FileChip";
import { MediaItem, MediaType } from "./MediaCard";
import { DocumentUploadModal } from "./DocumentUploadModal";

interface DocumentUploadFieldProps<T extends FieldValues> {
  control: Control<T>;
  name: Path<T>;
  propertyId?: string;
  maxFiles?: number;
  requiredTypes?: MediaType[];
  label?: string;
  description?: string;
  placeholder?: string;
  disabled?: boolean;
}

export function DocumentUploadField<T extends FieldValues>({
  control,
  name,
  propertyId,
  maxFiles = 20,
  requiredTypes = [],
  label = "Documents",
  description,
  placeholder = "Tap to upload documents",
  disabled = false,
}: DocumentUploadFieldProps<T>) {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <FormField
      control={control}
      name={name}
      rules={{
        validate: {
          required: (media: MediaItem[]) => {
            return media.length > 0 || "Please upload at least one document";
          },
          noPending: (media: MediaItem[]) => {
            const pending = media.filter((m) =>
              ["idle", "compressing", "uploading"].includes(m.status)
            );
            return (
              pending.length === 0 ||
              `${pending.length} upload(s) still in progress`
            );
          },
          noErrors: (media: MediaItem[]) => {
            const errors = media.filter((m) => m.status === "error");
            return (
              errors.length === 0 ||
              `${errors.length} upload(s) failed. Please retry or remove.`
            );
          },
          hasMetadata: (media: MediaItem[]) => {
            const incomplete = media.filter(
              (m) => !m.metadata.type || m.metadata.title.trim().length < 3
            );
            return (
              incomplete.length === 0 ||
              `${incomplete.length} document(s) missing details`
            );
          },
          requiredTypes: (media: MediaItem[]) => {
            if (requiredTypes.length === 0) return true;
            const uploadedTypes = media
              .filter((m) => m.status === "done")
              .map((m) => m.metadata.type);
            const missing = requiredTypes.filter(
              (t) => !uploadedTypes.includes(t)
            );
            return (
              missing.length === 0 || `Missing required: ${missing.join(", ")}`
            );
          },
        },
      }}
      render={({ field }) => {
        const mediaItems = (field.value as MediaItem[]) || [];
        const doneCount = mediaItems.filter((m) => m.status === "done").length;
        const pendingCount = mediaItems.filter((m) =>
          ["idle", "compressing", "uploading"].includes(m.status)
        ).length;
        const errorCount = mediaItems.filter(
          (m) => m.status === "error"
        ).length;

        const handleRemove = useCallback(
          (mediaId: string) => {
            const updatedMedia = mediaItems.filter((m) => m.id !== mediaId);
            const removedMedia = mediaItems.find((m) => m.id === mediaId);
            if (removedMedia?.preview.startsWith("blob:")) {
              URL.revokeObjectURL(removedMedia.preview);
            }
            field.onChange(updatedMedia);
          },
          [mediaItems, field]
        );

        const handleSave = useCallback(
          (updatedMedia: MediaItem[]) => {
            field.onChange(updatedMedia);
          },
          [field]
        );

        return (
          <FormItem>
            <FormLabel className="text-base sm:text-sm">{label}</FormLabel>
            <FormControl>
              <div className="space-y-3 sm:space-y-2">
                <div
                  onClick={() => !disabled && setModalOpen(true)}
                  onKeyDown={(e) => {
                    if ((e.key === "Enter" || e.key === " ") && !disabled) {
                      e.preventDefault();
                      setModalOpen(true);
                    }
                  }}
                  tabIndex={disabled ? -1 : 0}
                  role="button"
                  aria-label={`Upload documents. ${mediaItems.length} document(s) selected`}
                  aria-disabled={disabled}
                  className={cn(
                    "p-4 sm:p-3 border-2 rounded-xl sm:rounded-lg transition-all",
                    "min-h-[100px] sm:min-h-[80px]",
                    !disabled && "cursor-pointer hover:border-primary",
                    !disabled &&
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                    disabled && "opacity-50 cursor-not-allowed",
                    mediaItems.length === 0 && "border-dashed",
                    mediaItems.length > 0 && "border-solid"
                  )}
                >
                  {mediaItems.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center py-4 sm:py-2">
                      <Upload className="h-8 w-8 sm:h-6 sm:w-6 text-muted-foreground mb-2 sm:mb-1" />
                      <p className="text-sm sm:text-sm text-muted-foreground">
                        {placeholder}
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-3 sm:space-y-2">
                      <div className="flex flex-wrap gap-2">
                        {mediaItems.map((media) => (
                          <FileChip
                            key={media.id}
                            filename={media.filename}
                            status={media.status}
                            onRemove={() => handleRemove(media.id)}
                          />
                        ))}
                      </div>

                      <div className="flex flex-col sm:flex-row sm:items-center gap-2 text-xs text-muted-foreground">
                        <span className="font-medium">
                          {doneCount} of {mediaItems.length} ready
                        </span>
                        {pendingCount > 0 && (
                          <span className="flex items-center gap-1 text-amber-700 dark:text-amber-400">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            {pendingCount} uploading
                          </span>
                        )}
                        {errorCount > 0 && (
                          <span className="flex items-center gap-1 text-destructive">
                            <AlertCircle className="h-3 w-3" />
                            {errorCount} failed
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* <Button
                  type="button"
                  variant="outline"
                  size="lg"
                  onClick={() => setModalOpen(true)}
                  disabled={disabled}
                  className="w-full sm:w-auto"
                >
                  <Upload className="mr-2 h-4 w-4" />
                  {mediaItems.length === 0 ? 'Upload Documents' : 'Add More'}
                </Button> */}

                <DocumentUploadModal
                  open={modalOpen}
                  onOpenChange={setModalOpen}
                  mediaItems={mediaItems}
                  onSave={handleSave}
                  propertyId={propertyId}
                  maxFiles={maxFiles}
                  requiredTypes={requiredTypes}
                />
              </div>
            </FormControl>
            {description && (
              <FormDescription className="text-sm sm:text-xs">
                {description}
              </FormDescription>
            )}
            <div className="text-sm sm:text-xs">
              <ul className="list-disc pl-4">
                {requiredTypes.map((type, key) => (
                  <li key={key}>{type.title}</li>
                ))}
              </ul>
            </div>
            <FormMessage />
          </FormItem>
        );
      }}
    />
  );
}

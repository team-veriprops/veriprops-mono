import { useState, useEffect } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { useIsMobile } from '@hooks/use-mobile';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@3rdparty/ui/dialog';
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
  DrawerFooter,
} from '@3rdparty/ui/drawer';
import { Button } from '@3rdparty/ui/button';
import { MediaUploadManager } from './MediaUploadManager';
import { MediaItem, MediaType } from './MediaCard';

interface DocumentUploadModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mediaItems: MediaItem[];
  onSave: (media: MediaItem[]) => void;
  propertyId?: string;
  maxFiles?: number;
  requiredTypes?: MediaType[];
}

export function DocumentUploadModal({
  open,
  onOpenChange,
  mediaItems,
  onSave,
  propertyId,
  maxFiles = 20,
  requiredTypes = [],
}: DocumentUploadModalProps) {
  const isMobile = useIsMobile();
  const [localMedia, setLocalMedia] = useState<MediaItem[]>(mediaItems);

  useEffect(() => {
    if (open) {
      setLocalMedia(mediaItems);
    }
  }, [open, mediaItems]);

  const canSave =
    localMedia.length > 0 &&
    localMedia.every((m) => m.status === 'done') &&
    localMedia.every((m) => m.metadata.type && m.metadata.title.trim().length >= 3);

  const getMissingRequiredTypes = (): MediaType[] => {
    if (!requiredTypes || requiredTypes.length === 0) return [];
    const uploadedTypes = localMedia
      .filter((m) => m.status === 'done' && m.metadata.type)
      .map((m) => m.metadata.type as MediaType);
    return requiredTypes.filter((reqType) => !uploadedTypes.includes(reqType));
  };

  const missingTypes = getMissingRequiredTypes();
  const isValid = canSave && missingTypes.length === 0;

  const handleSave = () => {
    if (isValid) {
      onSave(localMedia);
      onOpenChange(false);
    }
  };

  const handleCancel = () => {
    setLocalMedia(mediaItems);
    onOpenChange(false);
  };

  const content = (
    <div className="flex-1 overflow-y-auto py-4">
      <MediaUploadManager
        propertyId={propertyId}
        maxFiles={maxFiles}
        requiredTypes={requiredTypes}
        seedMedia={localMedia}
        onChange={setLocalMedia}
        hideSubmit
        mode="modal"
      />
    </div>
  );

  const footer = (
    <div className="flex gap-3 sm:gap-2">
      <Button
        variant="outline"
        onClick={handleCancel}
        className="flex-1"
        type="button"
      >
        Cancel
      </Button>
      <Button
        onClick={handleSave}
        disabled={!isValid}
        className="flex-1"
        type="button"
      >
        <CheckCircle2 className="mr-2 h-4 w-4" />
        Save Documents ({localMedia.filter(m => m.status === 'done').length})
      </Button>
    </div>
  );

  if (isMobile) {
    return (
      <Drawer open={open} onOpenChange={onOpenChange}>
        <DrawerContent className="max-h-[95vh] flex flex-col">
          <DrawerHeader className="text-left">
            <DrawerTitle>Upload Documents</DrawerTitle>
            <DrawerDescription>
              Upload and manage your documents
            </DrawerDescription>
          </DrawerHeader>
          <div className="flex-1 overflow-auto p-4 sm:p-6">{content}</div>
          <DrawerFooter className="pt-2">{footer}</DrawerFooter>
        </DrawerContent>
      </Drawer>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="
        !max-w-none
      w-[95vw] sm:w-[90vw] lg:w-[75vw] 
      h-[95vh] sm:h-auto max-h-[95vh]
      flex flex-col
      
      rounded-none sm:rounded-xl
    "
      >
        <DialogHeader className="pb-2">
          <DialogTitle className="text-lg sm:text-xl font-semibold">
            Upload Documents
          </DialogTitle>
          <DialogDescription className="text-sm sm:text-base">
            Upload and manage your documents. All documents must be successfully
            uploaded and have complete metadata before saving.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 pr-4 overflow-auto">{content}</div>

        <DialogFooter className="pt-3 sm:pt-4">{footer}</DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

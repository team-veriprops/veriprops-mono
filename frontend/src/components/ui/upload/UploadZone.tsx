import { useCallback, useRef, useState } from 'react';
import { Upload, Camera, FolderOpen } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@3rdparty/ui/button';
import { cn } from '@lib/utils';

interface UploadZoneProps {
  onFilesSelected: (files: FileList) => void;
  maxFiles?: number;
  currentFileCount?: number;
  disabled?: boolean;
  className?: string;
}

export function UploadZone({
  onFilesSelected,
  maxFiles = 20,
  currentFileCount = 0,
  disabled = false,
  className,
}: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  const remainingSlots = maxFiles - currentFileCount;
  const canUpload = remainingSlots > 0 && !disabled;

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (canUpload) {
        setIsDragging(true);
      }
    },
    [canUpload]
  );

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      if (!canUpload) return;

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        onFilesSelected(files);
      }
    },
    [canUpload, onFilesSelected]
  );

  const handleFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        onFilesSelected(files);
      }
      // Reset input
      if (fileInputRef.current) fileInputRef.current.value = '';
      if (cameraInputRef.current) cameraInputRef.current.value = '';
    },
    [onFilesSelected]
  );

  const openFilePicker = useCallback(() => {
    if (canUpload) {
      fileInputRef.current?.click();
    }
  }, [canUpload]);

  const openCamera = useCallback(() => {
    if (canUpload) {
      cameraInputRef.current?.click();
    }
  }, [canUpload]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.key === 'Enter' || e.key === ' ') && canUpload) {
        e.preventDefault();
        openFilePicker();
      }
    },
    [canUpload, openFilePicker]
  );

  return (
    <div className={cn('w-full', className)}>
      {/* Hidden file inputs */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept="image/*,application/pdf,video/*"
        onChange={handleFileInputChange}
        className="hidden"
        aria-label="Upload images, PDFs, and videos from device"
      />
      <input
        ref={cameraInputRef}
        type="file"
        multiple
        accept="image/*,application/pdf,video/*"
        capture="environment"
        onChange={handleFileInputChange}
        className="hidden"
        aria-label="Capture images and videos with camera"
      />

      {/* Desktop drag & drop zone */}
      <motion.div
        role="button"
        tabIndex={canUpload ? 0 : -1}
        aria-label="Drag and drop images or click to upload"
        aria-disabled={!canUpload}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={openFilePicker}
        onKeyDown={handleKeyDown}
        className={cn(
          'hidden md:flex flex-col items-center justify-center',
          'min-h-[240px] rounded-xl border-2 border-dashed',
          'transition-all duration-200 cursor-pointer',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          isDragging && canUpload
            ? 'border-primary bg-upload-zone-bg scale-[1.02]'
            : 'border-upload-zone-border bg-card hover:border-primary/60 hover:bg-upload-zone-bg/50',
          !canUpload && 'opacity-50 cursor-not-allowed hover:border-upload-zone-border'
        )}
        whileHover={canUpload ? { scale: 1.01 } : {}}
        whileTap={canUpload ? { scale: 0.99 } : {}}
      >
        <AnimatePresence mode="wait">
          {isDragging ? (
            <motion.div
              key="dragging"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.8, opacity: 0 }}
              className="flex flex-col items-center gap-3"
            >
              <div className="relative">
                <Upload className="h-12 w-12 text-primary" />
                <motion.div
                  className="absolute inset-0 rounded-full bg-primary/20"
                  animate={{ scale: [1, 1.3, 1] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
              </div>
              <p className="text-lg font-medium text-primary">Drop images here</p>
            </motion.div>
          ) : (
            <motion.div
              key="idle"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.8, opacity: 0 }}
              className="flex flex-col items-center gap-4 px-6 text-center"
            >
              <div className="p-4 rounded-full bg-upload-zone-bg">
                <Upload className="h-8 w-8 text-primary" />
              </div>
              <div>
                <p className="text-lg font-medium text-foreground">
                  Drag & drop files here
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  or click to browse files
                </p>
              </div>
              <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                <span>Images, PDFs & Videos accepted</span>
                <span>•</span>
                <span>Max 10MB images, 20MB PDFs, 100MB videos</span>
                <span>•</span>
                <span>{remainingSlots} slots remaining</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      <div className="flex md:hidden gap-3">
        <Button
          variant="outline"
          size="lg"
          onClick={openCamera}
          disabled={!canUpload}
          className="flex-1 h-auto py-6 flex-col gap-2"
          aria-label="Capture image with camera"
        >
          <Camera className="h-6 w-6" />
          <span>Camera</span>
        </Button>
        <Button
          variant="outline"
          size="lg"
          onClick={openFilePicker}
          disabled={!canUpload}
          className="flex-1 h-auto py-6 flex-col gap-2"
          aria-label="Choose image from gallery"
        >
          <FolderOpen className="h-6 w-6" />
          <span>Gallery</span>
        </Button>
      </div>

      {!canUpload && (
        <p className="text-sm text-muted-foreground text-center mt-3" role="alert">
          Maximum number of images reached ({maxFiles})
        </p>
      )}
    </div>
  );
}

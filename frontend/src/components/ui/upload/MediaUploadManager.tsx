import { useState, useCallback, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, CheckCircle2, AlertTriangle, XCircle, AlertCircle, Loader2 } from 'lucide-react';
import imageCompression from 'browser-image-compression';
import { Button } from '@3rdparty/ui/button';
import { UploadZone } from './UploadZone';
import { MediaCard, MediaItem, MediaMetadata, MediaType } from './MediaCard';
import {
  validateFile,
  requestSignedUrl,
  uploadToSignedUrl,
  trackEvent,
} from '@lib/uploadService';
import { cn } from '@lib/utils';
import { Alert, AlertDescription, AlertTitle } from '@3rdparty/ui/alert';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@3rdparty/ui/tooltip';
import { toast } from '@components/3rdparty/ui/use-toast';

interface MediaUploadManagerProps {
  propertyId?: string;
  maxFiles?: number;
  onSubmit?: (media: MediaMetadata[]) => void;
  onChange?: (media: MediaItem[]) => void;
  seedMedia?: MediaItem[];
  requiredTypes?: MediaType[];
  hideSubmit?: boolean;
  mode?: 'standalone' | 'modal';
}

export function MediaUploadManager({
  propertyId = 'demo-property',
  maxFiles = 20,
  onSubmit,
  onChange,
  seedMedia = [],
  requiredTypes = [],
  hideSubmit = false,
  mode = 'standalone',
}: MediaUploadManagerProps) {
  const [mediaItems, setMediaItems] = useState<MediaItem[]>(seedMedia);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const abortControllersRef = useRef<Map<string, AbortController>>(new Map());
  const blobUrlsRef = useRef<Set<string>>(new Set());
  const [uploadStats, setUploadStats] = useState<{
    [mediaId: string]: {
      startTime: number;
      lastLoaded: number;
      lastTime: number;
      speed: number;
    };
  }>({});

  // Cleanup object URLs on unmount
  useEffect(() => {
    return () => {
      blobUrlsRef.current.forEach((url) => {
        URL.revokeObjectURL(url);
      });
      blobUrlsRef.current.clear();
    };
  }, []);

  // Offline detection with auto-retry
  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      toast({
        title: 'Back online',
        description: 'Your connection has been restored. Retrying failed uploads...',
      });
      mediaItems.forEach((media) => {
        if (media.status === 'error' && media.file) {
          processUpload(media);
        }
      });
    };

    const handleOffline = () => {
      setIsOnline(false);
      toast({
        title: "You're offline",
        description: 'Uploads will resume when your connection is restored.',
        variant: 'destructive',
      });
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [mediaItems]);

  // Emit onChange when mediaItems change
  useEffect(() => {
    if (onChange) {
      onChange(mediaItems);
    }
  }, [mediaItems, onChange]);

  const handleFilesSelected = useCallback(
    (fileList: FileList) => {
      const files = Array.from(fileList);

      // Check if we exceed max files
      if (mediaItems.length + files.length > maxFiles) {
        toast({
          title: 'Too many files',
          description: `You can only upload ${maxFiles} files total. ${maxFiles - mediaItems.length} slots remaining.`,
          variant: 'destructive',
        });
        return;
      }

      const newMediaItems: MediaItem[] = [];

      files.forEach((file) => {
        // Validate file
        const validation = validateFile(file);
        if (!validation.valid) {
          toast({
            title: 'Invalid file',
            description: validation.error,
            variant: 'destructive',
          });
          return;
        }

        // Create media entry
        const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const preview = URL.createObjectURL(file);
        blobUrlsRef.current.add(preview);

        newMediaItems.push({
          id,
          file,
          preview,
          filename: file.name,
          size: file.size,
          status: 'idle',
          progress: 0,
          metadata: {
            type: null,
            title: '',
            description: '',
          },
        });

        trackEvent('upload_start', {
          id,
          filename: file.name,
          size: file.size,
        });
      });

      if (newMediaItems.length > 0) {
        setMediaItems((prev) => [...prev, ...newMediaItems]);
        // Auto-start upload
        newMediaItems.forEach((media) => {
          processUpload(media);
        });
      }
    },
    [mediaItems.length, maxFiles]
  );

  const updateMediaStatus = useCallback(
    (id: string, updates: Partial<MediaItem>) => {
      setMediaItems((prev) =>
        prev.map((m) => (m.id === id ? { ...m, ...updates } : m))
      );
    },
    []
  );

  const processUpload = useCallback(async (media: MediaItem) => {
    if (!media.file) return;

    const controller = new AbortController();
    abortControllersRef.current.set(media.id, controller);
    const startTime = Date.now();

    try {
      // Detect if file is PDF or video
      const isPdf = media.file.type === 'application/pdf';
      const isVideo = media.file.type.startsWith('video/');
      let fileToUpload: File | Blob = media.file;

      if (isPdf || isVideo) {
        // Skip compression for PDFs and videos
        updateMediaStatus(media.id, { status: 'uploading', progress: 30 });
      } else {
        // Step 1: Compression (images only)
        updateMediaStatus(media.id, { status: 'compressing', progress: 10 });

        const compressedFile = await imageCompression(media.file, {
          maxSizeMB: 1,
          maxWidthOrHeight: 1280,
          useWebWorker: true,
          exifOrientation: 1,
          onProgress: (progress) => {
            const mappedProgress = 10 + Math.round(progress * 0.2);
            updateMediaStatus(media.id, { progress: mappedProgress });
          },
        });

        fileToUpload = compressedFile;
        updateMediaStatus(media.id, { progress: 30 });
      }

      // Step 2: Request signed URL
      const signedUrlResponse = await requestSignedUrl({
        filename: media.filename,
        contentType: fileToUpload.type,
        folder: `properties/${propertyId}`,
      });

      // Step 3: Upload to signed URL
      updateMediaStatus(media.id, { status: 'uploading', progress: 35 });

      await uploadToSignedUrl(fileToUpload, signedUrlResponse.uploadUrl, {
        signal: controller.signal,
        onProgress: (progress) => {
          const mappedProgress = 35 + Math.round(progress.percent * 0.65);
          const now = Date.now();
          
          const stats = uploadStats[media.id] || {
            startTime: now,
            lastLoaded: 0,
            lastTime: now,
            speed: 0,
          };
          
          const timeDiff = (now - stats.lastTime) / 1000;
          const bytesDiff = progress.loaded - stats.lastLoaded;
          
          if (timeDiff > 0.5) {
            const instantSpeed = bytesDiff / timeDiff;
            const speed = stats.speed === 0 ? instantSpeed : stats.speed * 0.7 + instantSpeed * 0.3;
            
            const remaining = progress.total - progress.loaded;
            const estimatedTimeRemaining = speed > 0 ? remaining / speed : 0;
            
            setUploadStats(prev => ({
              ...prev,
              [media.id]: {
                startTime: stats.startTime,
                lastLoaded: progress.loaded,
                lastTime: now,
                speed,
              },
            }));
            
            updateMediaStatus(media.id, {
              progress: mappedProgress,
              uploadSpeed: speed,
              estimatedTimeRemaining,
            });
          } else {
            updateMediaStatus(media.id, { progress: mappedProgress });
          }
        },
        onExpiredUrl: async () => {
          console.log('Requesting fresh signed URL for', media.filename);
          const freshData = await requestSignedUrl({
            filename: media.filename,
            contentType: fileToUpload.type,
            folder: `properties/${propertyId}`,
          });
          return freshData.uploadUrl;
        },
      });

      // Success
      const duration = Date.now() - startTime;
      setUploadStats(prev => {
        const newStats = { ...prev };
        delete newStats[media.id];
        return newStats;
      });
      updateMediaStatus(media.id, {
        status: 'done',
        progress: 100,
        uploadedUrl: signedUrlResponse.publicUrl,
        estimatedTimeRemaining: 0,
      });

      trackEvent('upload_complete', {
        id: media.id,
        filename: media.filename,
        bytes: media.size,
        duration,
        publicUrl: signedUrlResponse.publicUrl,
        fileType: isVideo ? 'video' : isPdf ? 'pdf' : 'image',
      });

      toast({
        title: 'Upload successful',
        description: `${media.filename} uploaded successfully`,
      });
    } catch (error: any) {
      if (error.name === 'AbortError') {
        return;
      }

      if (error.status === 409) {
        toast({
          title: 'Duplicate file detected',
          description: 'This file may already exist.',
        });
        updateMediaStatus(media.id, {
          status: 'done',
          progress: 100,
          uploadedUrl: error.existingUrl || media.uploadedUrl,
        });
        return;
      }

      const errorMessage =
        error.message === 'Upload cancelled'
          ? 'Upload cancelled'
          : error.message || 'Network error during upload';

      updateMediaStatus(media.id, {
        status: 'error',
        error: errorMessage,
      });

      trackEvent('upload_fail', {
        id: media.id,
        filename: media.filename,
        error: errorMessage,
      });

      if (error.message !== 'Upload cancelled') {
        toast({
          title: 'Upload failed',
          description: errorMessage,
          variant: 'destructive',
        });
      }
    } finally {
      abortControllersRef.current.delete(media.id);
    }
  }, [propertyId, updateMediaStatus]);

  const handleDelete = useCallback((id: string) => {
    const controller = abortControllersRef.current.get(id);
    if (controller) {
      controller.abort();
      abortControllersRef.current.delete(id);
    }

    setMediaItems((prev) => {
      const media = prev.find((m) => m.id === id);
      if (media && media.preview.startsWith('blob:')) {
        URL.revokeObjectURL(media.preview);
        blobUrlsRef.current.delete(media.preview);
      }
      return prev.filter((m) => m.id !== id);
    });
  }, []);

  const handleCancel = useCallback((id: string) => {
    const controller = abortControllersRef.current.get(id);
    if (controller) {
      controller.abort();
      abortControllersRef.current.delete(id);
      updateMediaStatus(id, { 
        status: 'idle', 
        progress: 0, 
        error: undefined 
      });
      toast({
        title: 'Upload cancelled',
        description: 'You can retry when ready',
      });
    }
  }, [updateMediaStatus]);

  const handleCancelAll = useCallback(() => {
    const cancelledCount = abortControllersRef.current.size;
    abortControllersRef.current.forEach((controller) => {
      controller.abort();
    });
    abortControllersRef.current.clear();
    
    setMediaItems((prev) =>
      prev.map((m) =>
        m.status === 'compressing' || m.status === 'uploading'
          ? { ...m, status: 'idle', progress: 0, error: undefined }
          : m
      )
    );

    if (cancelledCount > 0) {
      toast({
        title: 'All uploads cancelled',
        description: `${cancelledCount} upload${cancelledCount > 1 ? 's' : ''} cancelled`,
      });
    }
  }, []);

  const handleRetry = useCallback(
    (id: string) => {
      const media = mediaItems.find((m) => m.id === id);
      if (media) {
        updateMediaStatus(id, { status: 'idle', progress: 0, error: undefined });
        processUpload(media);
      }
    },
    [mediaItems, processUpload, updateMediaStatus]
  );

  const handleMetadataChange = useCallback(
    (id: string, metadata: Partial<MediaMetadata>) => {
      setMediaItems((prev) =>
        prev.map((m) =>
          m.id === id ? { ...m, metadata: { ...m.metadata, ...metadata } } : m
        )
      );
    },
    []
  );

  const getMissingRequiredTypes = useCallback((): MediaType[] => {
    if (!requiredTypes || requiredTypes.length === 0) return [];
    
    const uploadedTypes = mediaItems
      .filter((m) => m.status === 'done' && m.metadata.type)
      .map((m) => m.metadata.type as MediaType);
    
    return requiredTypes.filter(
      (reqType) => !uploadedTypes.includes(reqType)
    );
  }, [mediaItems, requiredTypes]);

  const missingTypes = getMissingRequiredTypes();

  const uploadingCount = mediaItems.filter(
    (m) => m.status === 'compressing' || m.status === 'uploading'
  ).length;
  const errorCount = mediaItems.filter((m) => m.status === 'error').length;
  const doneCount = mediaItems.filter((m) => m.status === 'done').length;

  const canSubmit = 
    mediaItems.length > 0 &&
    mediaItems.filter((m) => m.status !== 'error').every(
      (m) =>
        m.status === 'done' &&
        m.metadata.type &&
        m.metadata.title.trim().length >= 3
    ) &&
    missingTypes.length === 0;

  const handleSubmit = useCallback(async () => {
    if (!canSubmit) return;

    if (missingTypes.length > 0) {
      trackEvent('submit_blocked_missing_required_types', {
        property_id: propertyId,
        missing_types: missingTypes,
        uploaded_count: mediaItems.filter(m => m.status === 'done').length,
      });
      return;
    }

    setIsSubmitting(true);

    try {
      const payload = mediaItems
        .filter((m) => m.status === 'done')
        .map((m) => ({
          title: m.metadata.title.trim(),
          description: m.metadata.description.trim(),
          type: m.metadata.type,
          url: m.uploadedUrl!,
        }));

      trackEvent('metadata_saved', { 
        property_id: propertyId,
        count: payload.length,
        total_files: mediaItems.length,
        skipped_errors: errorCount
      });

      if (onSubmit) {
        onSubmit(payload);
      }

      toast({
        title: 'Files saved',
        description: `${payload.length} item${payload.length > 1 ? 's' : ''} saved successfully`,
      });

      // Clear media after successful submit
      mediaItems.forEach((media) => {
        if (media.preview.startsWith('blob:')) {
          URL.revokeObjectURL(media.preview);
          blobUrlsRef.current.delete(media.preview);
        }
      });
      setMediaItems([]);
    } catch (error: any) {
      toast({
        title: 'Save failed',
        description: error.message || 'Failed to save files',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  }, [canSubmit, mediaItems, propertyId, onSubmit, missingTypes, errorCount]);

  return (
    <div className={cn('w-full space-y-6', mode === 'modal' && 'space-y-4')}>
      {/* Upload zone */}
      <UploadZone
        onFilesSelected={handleFilesSelected}
        maxFiles={maxFiles}
        currentFileCount={mediaItems.length}
        disabled={!isOnline || mediaItems.length >= maxFiles}
      />

      {/* Media stats */}
      {mediaItems.length > 0 && (
        <div className="flex items-center gap-4 text-sm text-muted-foreground px-1">
          <div className="flex items-center gap-1.5">
            <Upload className="h-4 w-4" />
            <span className="font-medium">{mediaItems.length}</span>
            <span>
              file{mediaItems.length !== 1 ? 's' : ''}
            </span>
          </div>
          {uploadingCount > 0 && (
            <>
              <span>•</span>
              <div className="flex items-center gap-1.5 text-primary">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>{uploadingCount} uploading</span>
              </div>
            </>
          )}
          {doneCount > 0 && (
            <>
              <span>•</span>
              <div className="flex items-center gap-1.5 text-success">
                <CheckCircle2 className="h-4 w-4" />
                <span>{doneCount} done</span>
              </div>
            </>
          )}
          {errorCount > 0 && (
            <>
              <span>•</span>
              <div className="flex items-center gap-1.5 text-destructive">
                <AlertCircle className="h-4 w-4" />
                <span>{errorCount} failed</span>
              </div>
            </>
          )}
        </div>
      )}

      {/* Missing required types warning */}
      {missingTypes.length > 0 && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Missing required documents</AlertTitle>
          <AlertDescription>
            Please upload: {missingTypes.map((type) => type.title).join(', ')}
          </AlertDescription>
        </Alert>
      )}

      {/* Bulk actions */}
      {uploadingCount > 0 && (
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleCancelAll}
            className="gap-2"
          >
            <XCircle className="h-4 w-4" />
            Cancel All Uploads
          </Button>
        </div>
      )}

      {/* Media grid */}
      <AnimatePresence mode="popLayout">
        {mediaItems.length > 0 && (
          <motion.div
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
            layout
          >
            {mediaItems.map((media) => (
              <MediaCard
                key={media.id}
                media={media}
                onDelete={handleDelete}
                onRetry={handleRetry}
                onCancel={handleCancel}
                onMetadataChange={handleMetadataChange}
                requiredTypes={requiredTypes}
                aria-label={`Media card for ${media.filename}`}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Submit button */}
      {!hideSubmit && mediaItems.length > 0 && (
        <div className="flex justify-end pt-4">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <div>
                  <Button
                    onClick={handleSubmit}
                    disabled={!canSubmit || isSubmitting}
                    size="lg"
                    className="gap-2"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="h-5 w-5 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="h-5 w-5" />
                        Submit All ({doneCount})
                      </>
                    )}
                  </Button>
                </div>
              </TooltipTrigger>
              {!canSubmit && (
                <TooltipContent>
                  <p className="text-xs">
                    {missingTypes.length > 0
                      ? `Missing: ${missingTypes.map((type) => type.title).join(', ')}`
                      : uploadingCount > 0
                      ? `Wait for ${uploadingCount} upload${uploadingCount > 1 ? 's' : ''} to complete`
                      : errorCount > 0
                      ? `Fix or remove ${errorCount} failed upload${errorCount > 1 ? 's' : ''}`
                      : 'Complete all metadata fields'}
                  </p>
                </TooltipContent>
              )}
            </Tooltip>
          </TooltipProvider>
        </div>
      )}
    </div>
  );
}

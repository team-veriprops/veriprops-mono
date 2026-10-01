"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Camera, RefreshCw, Upload, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@3rdparty/ui/button";
import { getErrorMessage } from "@lib/errors";
import { fileToJpegBase64, jpegDataUrl, toJpegBase64 } from "@lib/image";

/** Which camera to open: the front one for a selfie, the back one for a document. */
export enum CameraFacing {
  USER = "user",
  ENVIRONMENT = "environment",
}

const noSubscription = () => () => {};
const hasCamera = () => !!navigator.mediaDevices?.getUserMedia;

interface Props {
  label: string;
  hint?: string;
  facing: CameraFacing;
  /** The photo as base64 JPEG, when one has been taken. */
  value?: string;
  onChange: (base64: string | undefined) => void;
  testId: string;
}

/**
 * Take a photo with the device camera — the front camera on a phone, the webcam on a desktop —
 * or choose one from the device when there is no camera or it is refused. Every photo is
 * resized and re-encoded as JPEG in the browser (`@lib/image`) before it is handed back.
 */
export function PhotoCapture({ label, hint, facing, value, onChange, testId }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  // Known only in the browser: the server render (and hydration) offers the upload alone.
  const cameraAvailable = useSyncExternalStore(noSubscription, hasCamera, () => false);

  // Attach the live stream, and always release the camera when it is no longer shown.
  useEffect(() => {
    if (videoRef.current && stream) videoRef.current.srcObject = stream;
    return () => stream?.getTracks().forEach((t) => t.stop());
  }, [stream]);

  const openCamera = async () => {
    try {
      setStream(await navigator.mediaDevices.getUserMedia({ video: { facingMode: facing }, audio: false }));
    } catch (err) {
      toast.error(getErrorMessage(err, "We couldn't open the camera. Allow camera access, or upload a photo instead."));
    }
  };

  const capture = () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    try {
      onChange(toJpegBase64(video, video.videoWidth, video.videoHeight));
    } catch (err) {
      toast.error(getErrorMessage(err, "We couldn't take the photo. Try again, or upload one."));
    }
    setStream(null);
  };

  const choose = async (file: File | undefined) => {
    if (!file) return;
    try {
      onChange(await fileToJpegBase64(file));
    } catch (err) {
      toast.error(getErrorMessage(err, "That file isn't a photo we can use. Choose a JPEG or PNG image."));
    }
  };

  return (
    <div className="space-y-2" data-testid={testId}>
      <p className="text-sm font-medium">{label}</p>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}

      {value ? (
        <div className="flex items-end gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element -- a local data URL, not an optimisable asset */}
          <img src={jpegDataUrl(value)} alt={`${label} preview`} data-testid={`${testId}-preview`}
            className="h-32 w-auto rounded-lg border object-cover" />
          <Button type="button" variant="outline" size="sm" onClick={() => onChange(undefined)} data-testid={`${testId}-retake`}>
            <RefreshCw className="size-4" aria-hidden /> Retake
          </Button>
        </div>
      ) : stream ? (
        <div className="space-y-2">
          <video ref={videoRef} autoPlay playsInline muted aria-label={`${label} camera`}
            className={`w-full max-w-sm rounded-lg border bg-black ${facing === CameraFacing.USER ? "-scale-x-100" : ""}`} />
          <div className="flex gap-2">
            <Button type="button" onClick={capture} data-testid={`${testId}-shutter`}>
              <Camera className="size-4" aria-hidden /> Take photo
            </Button>
            <Button type="button" variant="ghost" onClick={() => setStream(null)}>
              <X className="size-4" aria-hidden /> Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-2 sm:flex-row">
          {cameraAvailable && (
            <Button type="button" variant="outline" onClick={openCamera} data-testid={`${testId}-camera`}>
              <Camera className="size-4" aria-hidden /> Use camera
            </Button>
          )}
          <Button type="button" variant="outline" asChild>
            <label className="cursor-pointer">
              <Upload className="size-4" aria-hidden /> Upload a photo
              <input type="file" accept="image/jpeg,image/png" capture={facing} className="sr-only"
                onChange={(e) => { void choose(e.target.files?.[0]); e.target.value = ""; }}
                data-testid={`${testId}-file`} />
            </label>
          </Button>
        </div>
      )}
    </div>
  );
}

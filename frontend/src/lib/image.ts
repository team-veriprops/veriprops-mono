/**
 * Photos taken in the browser, sized for upload.
 *
 * Phone cameras produce 4–12 MB files; an identity check needs a clear face or document, not
 * the sensor's full resolution. Every photo is redrawn onto a canvas no larger than
 * `PHOTO_MAX_EDGE` pixels on its longer side and re-encoded as JPEG — which also strips the
 * camera's EXIF metadata (GPS, device) before anything leaves the device.
 */

/** Longest edge, in pixels, of a photo sent for identity checks. */
export const PHOTO_MAX_EDGE = 1280;
/** JPEG quality for those photos: small enough to send quickly, sharp enough to match a face. */
export const PHOTO_JPEG_QUALITY = 0.85;

/** The size an image of `width`×`height` is drawn at so neither edge exceeds `maxEdge`,
 * keeping its proportions and never enlarging it. */
export function fitWithin(width: number, height: number, maxEdge: number): { width: number; height: number } {
  const scale = Math.min(1, maxEdge / Math.max(width, height));
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) };
}

/** Base64 JPEG (no `data:` prefix) of `source`, drawn at most `PHOTO_MAX_EDGE` on its longer edge. */
export function toJpegBase64(source: CanvasImageSource, width: number, height: number): string {
  const size = fitWithin(width, height, PHOTO_MAX_EDGE);
  const canvas = document.createElement("canvas");
  canvas.width = size.width;
  canvas.height = size.height;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("This browser cannot prepare photos.");
  context.drawImage(source, 0, 0, size.width, size.height);
  return canvas.toDataURL("image/jpeg", PHOTO_JPEG_QUALITY).split(",", 2)[1];
}

/** Base64 JPEG of an image file chosen from the device, resized as above. */
export async function fileToJpegBase64(file: File): Promise<string> {
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    return toJpegBase64(image, image.naturalWidth, image.naturalHeight);
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** The `src` that shows a base64 JPEG. */
export const jpegDataUrl = (base64: string) => `data:image/jpeg;base64,${base64}`;

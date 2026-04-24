/**
 * Upload Service - Handles signed URL requests and file uploads
 * 
 * TODO: Replace these mock implementations with real API endpoints
 * - POST /api/uploads/sign for signed URL generation
 * - POST /api/properties/{propertyId}/photos for metadata persistence
 */

export interface SignedUrlRequest {
  filename: string;
  contentType: string;
  folder?: string;
}

export interface SignedUrlResponse {
  uploadUrl: string;
  publicUrl: string;
  expiresAt: string;
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percent: number;
}

export interface UploadOptions {
  onProgress?: (progress: UploadProgress) => void;
  signal?: AbortSignal;
  onExpiredUrl?: () => Promise<string>;
}

/**
 * Request a signed URL for direct upload to cloud storage
 * TODO: Replace with actual API endpoint
 */
export async function requestSignedUrl(
  request: SignedUrlRequest
): Promise<SignedUrlResponse> {
  // Simulate API call
  await new Promise((resolve) => setTimeout(resolve, 300));

  // Mock response - in production, this would call your backend
  const timestamp = Date.now();
  const mockPublicUrl = `https://cdn.veriprops.com/${request.folder || 'uploads'}/${timestamp}-${request.filename}`;

  return {
    uploadUrl: `https://storage.mock.com/signed-upload/${timestamp}`,
    publicUrl: mockPublicUrl,
    expiresAt: new Date(Date.now() + 3600000).toISOString(), // 1 hour
  };
}

/**
 * CLIENT-SIDE ENCRYPTION GUIDE (for sensitive documents)
 * 
 * ═══════════════════════════════════════════════════════════
 * When to use:
 * ═══════════════════════════════════════════════════════════
 * - PII (Personally Identifiable Information)
 * - Legal documents (C of O, Deeds, Receipts)
 * - Any document with regulatory compliance requirements (GDPR, HIPAA)
 * 
 * ═══════════════════════════════════════════════════════════
 * Recommended approach:
 * ═══════════════════════════════════════════════════════════
 * 1. Use Web Crypto API (built-in, no dependencies)
 * 2. Generate AES-GCM encryption key per-upload or per-user
 * 3. Encrypt file BEFORE compression
 * 4. Store encryption key securely (NEVER in localStorage)
 *    - Option A: Derive from user's password (PBKDF2)
 *    - Option B: Store in secure backend, fetch via authenticated API
 * 
 * ═══════════════════════════════════════════════════════════
 * Libraries (if not using Web Crypto API):
 * ═══════════════════════════════════════════════════════════
 * - Native: Web Crypto API (crypto.subtle) - RECOMMENDED
 * - Alternative: @noble/ciphers (lightweight, modern)
 * - AVOID: CryptoJS (outdated, large bundle, slow)
 * 
 * ═══════════════════════════════════════════════════════════
 * Security considerations:
 * ═══════════════════════════════════════════════════════════
 * - Never log encryption keys
 * - Never store keys in localStorage/sessionStorage
 * - Use HTTPS for all API requests
 * - Implement key rotation policy
 * - Add audit logging for key access
 * - Consider using envelope encryption for scalability
 */

/**
 * Upload file to signed URL with progress tracking and retry on expiration
 * Uses XHR for progress events and AbortController for cancellation
 */
export async function uploadToSignedUrl(
  file: Blob,
  signedUrl: string,
  options: UploadOptions = {}
): Promise<void> {
  let retryCount = 0;
  const MAX_RETRIES = 1;

  const attemptUpload = (url: string): Promise<void> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      if (options.signal) {
        options.signal.addEventListener('abort', () => {
          xhr.abort();
          reject(new Error('Upload cancelled'));
        });
      }

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable && options.onProgress) {
          options.onProgress({
            loaded: event.loaded,
            total: event.total,
            percent: Math.round((event.loaded / event.total) * 100),
          });
        }
      });

      xhr.addEventListener('load', async () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve();
        } else if (
          (xhr.status === 403 || xhr.status === 400) &&
          retryCount < MAX_RETRIES &&
          options.onExpiredUrl
        ) {
          retryCount++;
          console.log(`Signed URL expired (${xhr.status}), retrying with fresh URL...`);
          
          try {
            const freshUrl = await options.onExpiredUrl();
            resolve(await attemptUpload(freshUrl));
          } catch (retryError) {
            reject(new Error(`Retry failed: ${retryError}`));
          }
        } else {
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      });

      xhr.addEventListener('error', () => {
        reject(new Error('Network error during upload'));
      });

      xhr.addEventListener('abort', () => {
        reject(new Error('Upload cancelled'));
      });

      xhr.open('PUT', url);
      xhr.setRequestHeader('Content-Type', file.type);

      // Mock upload simulation
      setTimeout(() => {
        const mockProgressSteps = [0.2, 0.4, 0.6, 0.8, 1.0];
        let step = 0;

        const progressInterval = setInterval(() => {
          if (step >= mockProgressSteps.length) {
            clearInterval(progressInterval);
            const loadEvent = new Event('load');
            Object.defineProperty(xhr, 'status', { value: 200, writable: false });
            xhr.dispatchEvent(loadEvent);
            return;
          }

          if (options.onProgress) {
            const loaded = Math.round(file.size * mockProgressSteps[step]);
            options.onProgress({
              loaded,
              total: file.size,
              percent: Math.round(mockProgressSteps[step] * 100),
            });
          }
          step++;
        }, 400);

        if (options.signal) {
          options.signal.addEventListener('abort', () => {
            clearInterval(progressInterval);
          });
        }
      }, 100);
    });
  };

  return attemptUpload(signedUrl);
}

/**
 * Validate file before upload
 */
export interface ValidationResult {
  valid: boolean;
  error?: string;
}

const MAX_IMAGE_SIZE = 10 * 1024 * 1024;  // 10MB
const MAX_PDF_SIZE = 20 * 1024 * 1024;    // 20MB
const MAX_VIDEO_SIZE = 100 * 1024 * 1024; // 100MB
const ALLOWED_TYPES = [
  'image/jpeg', 
  'image/png', 
  'image/heic', 
  'image/heif', 
  'application/pdf',
  'video/mp4',
  'video/quicktime',
  'video/webm',
  'video/x-msvideo',
];

export function validateFile(file: File): ValidationResult {
  const isImage = ALLOWED_TYPES.includes(file.type) || file.type.startsWith('image/');
  const isPdf = file.type === 'application/pdf';
  const isVideo = file.type.startsWith('video/');
  
  // Check file type
  if (!isImage && !isPdf && !isVideo) {
    return {
      valid: false,
      error: 'Invalid file type. Only images (JPEG, PNG, HEIC), PDFs, and videos (MP4, MOV, WebM) are allowed.',
    };
  }

  // Check file size with appropriate limits
  let maxSize = MAX_IMAGE_SIZE;
  if (isPdf) maxSize = MAX_PDF_SIZE;
  if (isVideo) maxSize = MAX_VIDEO_SIZE;
  
  if (file.size > maxSize) {
    const fileType = isVideo ? 'Video' : isPdf ? 'PDF' : 'Image';
    return {
      valid: false,
      error: `${fileType} size exceeds ${maxSize / 1024 / 1024}MB limit. Current size: ${(file.size / 1024 / 1024).toFixed(1)}MB`,
    };
  }

  return { valid: true };
}

/**
 * Emit telemetry/analytics event
 * TODO: Replace console logs with real analytics SDK (Mixpanel, PostHog, etc.)
 */
export function trackEvent(
  eventName: string,
  properties: Record<string, any>
): void {
  console.log(`[Analytics] ${eventName}`, properties);
  // TODO: Implement real analytics
  // analytics.track(eventName, properties);
}

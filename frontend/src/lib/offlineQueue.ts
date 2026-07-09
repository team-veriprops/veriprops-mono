/**
 * IndexedDB-backed offline queue for agent form drafts and evidence uploads.
 * Used by the service worker Background Sync registration.
 */

const DB_NAME = "veriprops-offline";
const DB_VERSION = 1;
const STORE_DRAFTS = "drafts";
const STORE_UPLOADS = "uploads";

export interface DraftEntry {
  taskId: string;
  payload: Record<string, unknown>;
  savedAt: number;
}

export interface UploadEntry {
  id: string;
  taskId: string;
  fileBlob: Blob;
  fileName: string;
  mimeType: string;
  gpsLat?: number;
  gpsLng?: number;
  capturedAt?: string;
  queuedAt: number;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = (e.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(STORE_DRAFTS)) {
        db.createObjectStore(STORE_DRAFTS, { keyPath: "taskId" });
      }
      if (!db.objectStoreNames.contains(STORE_UPLOADS)) {
        db.createObjectStore(STORE_UPLOADS, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function tx<T>(
  db: IDBDatabase,
  store: string,
  mode: IDBTransactionMode,
  fn: (s: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const t = db.transaction(store, mode);
    const s = t.objectStore(store);
    const req = fn(s);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

// ── Drafts ─────────────────────────────────────────────────────────────

export async function saveDraftLocally(entry: DraftEntry): Promise<void> {
  const db = await openDb();
  await tx(db, STORE_DRAFTS, "readwrite", (s) => s.put(entry));
  db.close();
}

export async function getDraftLocally(taskId: string): Promise<DraftEntry | null> {
  const db = await openDb();
  const result = await tx<DraftEntry | undefined>(db, STORE_DRAFTS, "readonly", (s) => s.get(taskId));
  db.close();
  return result ?? null;
}

export async function clearDraftLocally(taskId: string): Promise<void> {
  const db = await openDb();
  await tx(db, STORE_DRAFTS, "readwrite", (s) => s.delete(taskId));
  db.close();
}

// ── Upload queue ────────────────────────────────────────────────────────

export async function enqueueUpload(entry: UploadEntry): Promise<void> {
  const db = await openDb();
  await tx(db, STORE_UPLOADS, "readwrite", (s) => s.put(entry));
  db.close();
  if ("serviceWorker" in navigator && "SyncManager" in window) {
    const reg = await navigator.serviceWorker.ready;
    await (reg as ServiceWorkerRegistration & { sync: { register(tag: string): Promise<void> } }).sync.register("evidence-upload");
  }
}

export async function getPendingUploads(): Promise<UploadEntry[]> {
  const db = await openDb();
  const result = await tx<UploadEntry[]>(db, STORE_UPLOADS, "readonly", (s) => s.getAll());
  db.close();
  return result;
}

export async function removeUpload(id: string): Promise<void> {
  const db = await openDb();
  await tx(db, STORE_UPLOADS, "readwrite", (s) => s.delete(id));
  db.close();
}

export async function pendingUploadCount(): Promise<number> {
  const db = await openDb();
  const result = await tx<number>(db, STORE_UPLOADS, "readonly", (s) => s.count());
  db.close();
  return result;
}

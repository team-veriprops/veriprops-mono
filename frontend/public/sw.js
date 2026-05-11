/**
 * Veriprops Agent Service Worker
 * Handles Background Sync for evidence upload queue.
 * Registered only in the agent surface (src/app/agents/layout.tsx).
 */

const CACHE_NAME = "veriprops-agent-v1";
const DB_NAME = "veriprops-offline";
const STORE_UPLOADS = "uploads";

// ── IndexedDB helpers (duplicated from offlineQueue.ts — SW runs in isolated scope) ──

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains("drafts")) {
        db.createObjectStore("drafts", { keyPath: "taskId" });
      }
      if (!db.objectStoreNames.contains(STORE_UPLOADS)) {
        db.createObjectStore(STORE_UPLOADS, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function getAllUploads(db) {
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE_UPLOADS, "readonly");
    const req = t.objectStore(STORE_UPLOADS).getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function deleteUpload(db, id) {
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE_UPLOADS, "readwrite");
    const req = t.objectStore(STORE_UPLOADS).delete(id);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

// ── SW lifecycle ──────────────────────────────────────────────────────

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

// ── Background Sync: flush evidence upload queue ──────────────────────

self.addEventListener("sync", (event) => {
  if (event.tag === "evidence-upload") {
    event.waitUntil(flushUploads());
  }
});

async function flushUploads() {
  const db = await openDb();
  const entries = await getAllUploads(db);

  for (const entry of entries) {
    try {
      const form = new FormData();
      form.append("file", entry.fileBlob, entry.fileName);
      if (entry.gpsLat != null) form.append("gps_lat", String(entry.gpsLat));
      if (entry.gpsLng != null) form.append("gps_lng", String(entry.gpsLng));
      if (entry.capturedAt) form.append("captured_at", entry.capturedAt);

      const res = await fetch(`/api/agents/tasks/${entry.taskId}/evidence`, {
        method: "POST",
        body: form,
        credentials: "include",
      });

      if (res.ok) {
        await deleteUpload(db, entry.id);
      }
    } catch (_) {
      // Will retry on next sync
    }
  }
  db.close();
}

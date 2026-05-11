"use client";

import { useEffect, useState } from "react";
import { pendingUploadCount } from "@lib/offlineQueue";
import { Wifi, WifiOff, CloudUpload, CheckCircle } from "lucide-react";

type SyncState = "online" | "offline" | "syncing" | "synced";

export default function SyncIndicator() {
  const [state, setState] = useState<SyncState>("online");
  const [pending, setPending] = useState(0);

  useEffect(() => {
    const update = async () => {
      const count = await pendingUploadCount();
      setPending(count);
      if (!navigator.onLine) {
        setState("offline");
      } else if (count > 0) {
        setState("syncing");
        // SW Background Sync will drain the queue; re-check after a moment
        setTimeout(update, 3000);
      } else {
        setState(prev => prev === "syncing" ? "synced" : "online");
      }
    };

    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  if (state === "online") return null;

  const configs: Record<SyncState, { icon: React.ReactNode; text: string; className: string }> = {
    online: { icon: null, text: "", className: "" },
    offline: {
      icon: <WifiOff className="h-3.5 w-3.5" />,
      text: "You're offline — changes saved locally",
      className: "bg-yellow-50 border-yellow-200 text-yellow-800",
    },
    syncing: {
      icon: <CloudUpload className="h-3.5 w-3.5 animate-pulse" />,
      text: `Syncing ${pending} item${pending !== 1 ? "s" : ""}…`,
      className: "bg-blue-50 border-blue-200 text-blue-800",
    },
    synced: {
      icon: <CheckCircle className="h-3.5 w-3.5" />,
      text: "All changes synced",
      className: "bg-green-50 border-green-200 text-green-800",
    },
  };

  const cfg = configs[state];

  return (
    <div className={`flex items-center gap-2 rounded border px-3 py-2 text-xs font-medium ${cfg.className}`}>
      {cfg.icon}
      <span>{cfg.text}</span>
    </div>
  );
}

"use client";

import { useState } from "react";
import { MapPin, FileText, Video, Image, X } from "lucide-react";
import type { Task } from "@components/admin/libs/admin-service";

interface EvidenceItem {
  id: string;
  type: "PHOTO" | "VIDEO" | "DOCUMENT";
  fileUrl: string;
  gpsLat: number | null;
  gpsLng: number | null;
  capturedAt: string | null;
  metadata: Record<string, unknown> | null;
}

interface Props {
  task: Task;
  evidence: EvidenceItem[];
}

const TYPE_ICON = {
  PHOTO: Image,
  VIDEO: Video,
  DOCUMENT: FileText,
};

export default function EvidenceGallery({ task, evidence }: Props) {
  const [selected, setSelected] = useState<EvidenceItem | null>(null);

  if (evidence.length === 0) {
    return (
      <p className="text-sm text-gray-400 italic py-4">
        No evidence uploaded for this task.
      </p>
    );
  }

  return (
    <>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {evidence.map((item) => {
          const Icon = TYPE_ICON[item.type];
          return (
            <button
              key={item.id}
              style={{ cursor: "pointer" }}
              onClick={() => setSelected(item)}
              className="group relative rounded-lg border border-gray-200 overflow-hidden aspect-square bg-gray-50 hover:border-indigo-400 transition-colors"
            >
              {item.type === "PHOTO" ? (
                <img
                  src={item.fileUrl}
                  alt="evidence"
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="flex flex-col items-center justify-center h-full gap-2 text-gray-400">
                  <Icon className="h-8 w-8" />
                  <span className="text-xs">{item.type}</span>
                </div>
              )}
              {item.gpsLat !== null && (
                <div className="absolute bottom-1 right-1 bg-white/80 rounded px-1 flex items-center gap-0.5">
                  <MapPin className="h-3 w-3 text-emerald-600" />
                  <span className="text-[10px] text-emerald-700">GPS</span>
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* Lightbox */}
      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
          <div className="relative max-w-3xl w-full mx-4 bg-white rounded-xl shadow-xl overflow-hidden">
            <button
              style={{ cursor: "pointer" }}
              onClick={() => setSelected(null)}
              className="absolute top-3 right-3 z-10 bg-white rounded-full p-1 shadow"
            >
              <X className="h-5 w-5 text-gray-700" />
            </button>

            {selected.type === "PHOTO" ? (
              <img src={selected.fileUrl} alt="evidence" className="w-full max-h-[70vh] object-contain" />
            ) : selected.type === "VIDEO" ? (
              <video src={selected.fileUrl} controls className="w-full max-h-[70vh]" />
            ) : (
              <div className="flex flex-col items-center gap-4 py-12">
                <FileText className="h-16 w-16 text-gray-400" />
                <a
                  href={selected.fileUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-indigo-600 underline text-sm"
                >
                  Open Document
                </a>
              </div>
            )}

            {/* Metadata panel */}
            <div className="px-4 py-3 border-t border-gray-100 bg-gray-50 text-xs text-gray-600 flex flex-wrap gap-4">
              <span><strong>Type:</strong> {selected.type}</span>
              <span><strong>Role:</strong> {task.role}</span>
              {selected.capturedAt && (
                <span><strong>Captured:</strong> {new Date(selected.capturedAt).toLocaleString()}</span>
              )}
              {selected.gpsLat !== null && selected.gpsLng !== null && (
                <span>
                  <MapPin className="inline h-3 w-3 mr-0.5 text-emerald-600" />
                  <strong>GPS:</strong> {selected.gpsLat.toFixed(6)}, {selected.gpsLng.toFixed(6)}
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

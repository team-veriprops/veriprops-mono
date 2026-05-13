"use client";

import { useState } from "react";
import Link from "next/link";
import { MapPin, FileText, Image, Video, X, ChevronLeft, ChevronRight } from "lucide-react";

interface EvidenceItem {
  id: string;
  evidenceType: string;
  fileUrl: string;
  gpsLat: number | null;
  gpsLng: number | null;
  capturedAt: string | null;
  agentRole: string;
}

const ROLE_COLORS: Record<string, string> = {
  FIELD: "bg-blue-100 text-blue-700",
  SURVEYOR: "bg-purple-100 text-purple-700",
  REGISTRY: "bg-green-100 text-green-700",
  LAWYER: "bg-orange-100 text-orange-700",
};

function TypeIcon({ type }: { type: string }) {
  if (type === "VIDEO") return <Video className="h-4 w-4" />;
  if (type === "DOCUMENT") return <FileText className="h-4 w-4" />;
  return <Image className="h-4 w-4" />;
}

function EvidenceViewer({ items, startIndex, onClose }: { items: EvidenceItem[]; startIndex: number; onClose: () => void }) {
  const [idx, setIdx] = useState(startIndex);
  const item = items[idx];

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" onClick={onClose}>
      <div className="relative max-w-3xl w-full bg-white rounded-xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <button onClick={onClose} className="absolute top-3 right-3 z-10 p-1 rounded-full bg-black/50 text-white hover:bg-black/70" style={{ cursor: "pointer" }}>
          <X className="h-5 w-5" />
        </button>
        {idx > 0 && (
          <button onClick={() => setIdx(i => i - 1)} className="absolute left-3 top-1/2 -translate-y-1/2 z-10 p-1.5 rounded-full bg-black/50 text-white" style={{ cursor: "pointer" }}>
            <ChevronLeft className="h-5 w-5" />
          </button>
        )}
        {idx < items.length - 1 && (
          <button onClick={() => setIdx(i => i + 1)} className="absolute right-3 top-1/2 -translate-y-1/2 z-10 p-1.5 rounded-full bg-black/50 text-white" style={{ cursor: "pointer" }}>
            <ChevronRight className="h-5 w-5" />
          </button>
        )}
        <div className="bg-gray-900 flex items-center justify-center min-h-64">
          {item.evidenceType === "PHOTO" ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={item.fileUrl} alt="Evidence" className="max-h-96 object-contain" />
          ) : item.evidenceType === "VIDEO" ? (
            <video src={item.fileUrl} controls className="max-h-96 w-full" />
          ) : (
            <Link href={item.fileUrl} target="_blank" rel="noopener noreferrer" className="text-white underline p-8">
              Open Document
            </Link>
          )}
        </div>
        <div className="p-4 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${ROLE_COLORS[item.agentRole] ?? "bg-gray-100 text-gray-600"}`}>
              {item.agentRole}
            </span>
            {item.capturedAt && (
              <span className="text-xs text-gray-400">{new Date(item.capturedAt).toLocaleString()}</span>
            )}
          </div>
          {item.gpsLat !== null && item.gpsLng !== null && (
            <div className="flex items-center gap-1 text-xs text-gray-500">
              <MapPin className="h-3.5 w-3.5" />
              {item.gpsLat.toFixed(6)}, {item.gpsLng.toFixed(6)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface Props {
  items: EvidenceItem[];
}

export default function EvidenceFeed({ items }: Props) {
  const [viewerIndex, setViewerIndex] = useState<number | null>(null);

  if (items.length === 0) {
    return <p className="text-sm text-gray-400 italic py-4">No evidence uploaded yet.</p>;
  }

  const grouped: Record<string, EvidenceItem[]> = {};
  for (const item of items) {
    if (!grouped[item.agentRole]) grouped[item.agentRole] = [];
    grouped[item.agentRole].push(item);
  }

  return (
    <>
      {Object.entries(grouped).map(([role, roleItems]) => (
        <div key={role} className="space-y-3">
          <h3 className={`text-xs font-semibold px-2 py-0.5 rounded-full inline-flex ${ROLE_COLORS[role] ?? "bg-gray-100 text-gray-600"}`}>
            {role}
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {roleItems.map((item) => {
              const globalIndex = items.indexOf(item);
              return (
                <button
                  key={item.id}
                  onClick={() => setViewerIndex(globalIndex)}
                  style={{ cursor: "pointer" }}
                  className="group relative aspect-square rounded-lg overflow-hidden border border-gray-200 bg-gray-50 hover:border-indigo-400"
                >
                  {item.evidenceType === "PHOTO" ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={item.fileUrl} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <div className="h-full w-full flex flex-col items-center justify-center gap-2 text-gray-400">
                      <TypeIcon type={item.evidenceType} />
                      <span className="text-xs">{item.evidenceType}</span>
                    </div>
                  )}
                  {item.gpsLat !== null && (
                    <div className="absolute top-1 right-1 p-0.5 rounded bg-black/50 text-white">
                      <MapPin className="h-3 w-3" />
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}

      {viewerIndex !== null && (
        <EvidenceViewer items={items} startIndex={viewerIndex} onClose={() => setViewerIndex(null)} />
      )}
    </>
  );
}

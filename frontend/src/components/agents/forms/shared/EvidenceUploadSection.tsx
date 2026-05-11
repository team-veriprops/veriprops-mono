"use client";

import { useRef, useState } from "react";
import { useUploadEvidenceMutation } from "../../libs/useAgentTaskQueries";
import { Camera, Upload, CheckCircle2 } from "lucide-react";

interface Props {
  taskId: string;
  minPhotos?: number;
  uploadedCount: number;
}

export default function EvidenceUploadSection({ taskId, minPhotos = 5, uploadedCount }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const upload = useUploadEvidenceMutation();
  const [localCount, setLocalCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const total = uploadedCount + localCount;
  const meetsMin = total >= minPhotos;

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setError(null);

    if (!navigator.geolocation) {
      setError("GPS is required but your browser does not support geolocation.");
      return;
    }

    const pos = await new Promise<GeolocationPosition | null>((res) => {
      navigator.geolocation.getCurrentPosition(res, () => res(null), { timeout: 5000 });
    });

    if (!pos) {
      setError("GPS location is required for photo evidence. Please enable location access.");
      return;
    }

    for (const file of Array.from(files)) {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("evidence_type", "PHOTO");
      fd.append("gps_lat", String(pos.coords.latitude));
      fd.append("gps_lng", String(pos.coords.longitude));
      fd.append("captured_at", new Date().toISOString());
      try {
        await upload.mutateAsync({ taskId, formData: fd });
        setLocalCount((c) => c + 1);
      } catch {
        setError("Failed to upload one or more photos.");
      }
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-gray-700">
          GPS-Stamped Photos
          <span className="text-red-500 ml-0.5">*</span>
          <span className="text-xs text-gray-400 ml-2">(min {minPhotos})</span>
        </label>
        <span className={`text-xs font-medium ${meetsMin ? "text-green-600" : "text-orange-500"}`}>
          {total} / {minPhotos} uploaded
          {meetsMin && <CheckCircle2 className="inline h-3 w-3 ml-1" />}
        </span>
      </div>

      <div
        onClick={() => fileRef.current?.click()}
        style={{ cursor: "pointer" }}
        className="flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-lg py-8 hover:border-indigo-400 hover:bg-indigo-50 transition-colors"
      >
        <Camera className="h-8 w-8 text-gray-400 mb-2" />
        <p className="text-sm text-gray-600">Click to take or upload photos</p>
        <p className="text-xs text-gray-400 mt-1">GPS coordinates will be captured automatically</p>
      </div>

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        multiple
        capture="environment"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />

      {upload.isPending && (
        <p className="text-xs text-indigo-600 animate-pulse">Uploading…</p>
      )}
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}

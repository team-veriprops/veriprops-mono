"use client";

import { useState, useRef, useCallback } from "react";
import { FileText, Loader2 } from "lucide-react";
import { reportService } from "./libs/report-service";

interface Props {
  vid: string;
  onAccepted: () => void;
}

export default function AccessGateModal({ vid, onAccepted }: Props) {
  const [scrolledToBottom, setScrolledToBottom] = useState(false);
  const [accepting, setAccepting] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);

  const handleScroll = useCallback(() => {
    const el = bodyRef.current;
    if (!el) return;
    const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 20;
    if (atBottom) setScrolledToBottom(true);
  }, []);

  async function handleAccept() {
    setAccepting(true);
    try {
      await reportService.acknowledge(vid);
      onAccepted();
    } catch {
      setAccepting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-lg bg-white rounded-xl shadow-2xl overflow-hidden">
        <div className="p-6 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <FileText className="h-6 w-6 text-indigo-600" />
            <h2 className="text-lg font-semibold text-gray-900">Property Verification Report</h2>
          </div>
          <p className="mt-2 text-sm text-gray-600">
            Please read and accept the terms below to access your report.
          </p>
        </div>

        <div
          ref={bodyRef}
          onScroll={handleScroll}
          className="max-h-60 overflow-y-auto p-6 text-sm text-gray-600 space-y-3"
        >
          <p>
            This verification report has been prepared by Veriprops and its network of licensed
            agents. The findings contained herein represent professional opinions based on
            observations and records available at the time of investigation.
          </p>
          <p>
            This report does not constitute a legal guarantee of title, ownership, or property
            condition. It is advisory in nature and should be used alongside independent legal counsel
            before completing any property transaction.
          </p>
          <p>
            By accepting, you acknowledge that you have read and understood the scope and limitations
            of this report. You agree not to redistribute or publish this report without the written
            consent of Veriprops.
          </p>
          <p className="font-medium text-gray-700">
            Veriprops is not liable for decisions made solely on the basis of this report.
          </p>
        </div>

        <div className="p-6 bg-gray-50 border-t border-gray-100">
          {!scrolledToBottom && (
            <p className="text-xs text-gray-400 mb-3">Scroll to the bottom to enable acceptance.</p>
          )}
          <button
            onClick={handleAccept}
            disabled={!scrolledToBottom || accepting}
            style={{ cursor: scrolledToBottom && !accepting ? "pointer" : "not-allowed" }}
            className="w-full flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {accepting && <Loader2 className="h-4 w-4 animate-spin" />}
            I Accept — View Report
          </button>
        </div>
      </div>
    </div>
  );
}

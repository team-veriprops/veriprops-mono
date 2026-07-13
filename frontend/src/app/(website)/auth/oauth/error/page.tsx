"use client";

import { CheckCircle2, X } from "lucide-react";

export default function OAuthErrorPage() {
  return (
    <div
      className="min-h-screen flex items-center justify-center p-6 bg-[#0b0d10]"
    >
      <div className="max-w-sm w-full text-center">
        <div
          className="w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-6 bg-red-600/15 border border-red-600/30"
        >
          <X className="w-7 h-7 text-red-400" />
        </div>

        <div className="flex items-center justify-center gap-2 mb-4">
          <div
            className="w-6 h-6 rounded-md flex items-center justify-center signature-gradient"
          >
            <CheckCircle2 className="w-3.5 h-3.5 text-white" strokeWidth={2.5} />
          </div>
          <span className="text-sm font-bold text-white/50">
            Veriprops
          </span>
        </div>

        <h1 className="text-xl font-bold text-white mb-3">Sign-in failed</h1>
        <p className="text-sm leading-relaxed mb-8 text-white/50">
          Something went wrong during sign-in. You can close this window and try again.
        </p>

        <button
          onClick={() => {
            try { window.close(); } catch { /* ignore */ }
          }}
          className="w-full py-3 rounded-xl text-sm font-semibold transition-all duration-200 hover:opacity-80 bg-white/8 text-white border border-white/12"
        >
          Close window
        </button>
      </div>
    </div>
  );
}

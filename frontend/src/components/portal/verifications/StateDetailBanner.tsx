"use client";

import Link from "next/link";
import { CheckCircle2, Clock, Eye, AlertCircle, FileText } from "lucide-react";
import { ROUTES } from "@lib/routes";

const BANNERS: Record<string, { icon: React.ReactNode; bg: string; text: string; extra?: React.ReactNode }> = {
  PAID: {
    icon: <Clock className="h-5 w-5 text-blue-600" />,
    bg: "bg-blue-50 border-blue-100",
    text: "Your verification is paid. We are assigning agents to begin work.",
  },
  IN_PROGRESS: {
    icon: <Eye className="h-5 w-5 text-indigo-600" />,
    bg: "bg-indigo-50 border-indigo-100",
    text: "Our agents are actively working on your property verification.",
  },
  UNDER_REVIEW: {
    icon: <FileText className="h-5 w-5 text-purple-600" />,
    bg: "bg-purple-50 border-purple-100",
    text: "All agent findings have been submitted and are under admin review.",
  },
  COMPLETED: {
    icon: <CheckCircle2 className="h-5 w-5 text-green-600" />,
    bg: "bg-green-50 border-green-100",
    text: "Your report is ready.",
  },
  FAILED: {
    icon: <AlertCircle className="h-5 w-5 text-red-600" />,
    bg: "bg-red-50 border-red-100",
    text: "This verification could not be completed. Please contact support.",
  },
};

interface Props {
  status: string;
  verificationId: string;
}

export default function StateDetailBanner({ status, verificationId }: Props) {
  const banner = BANNERS[status];
  if (!banner) return null;

  return (
    <div className={`flex items-start gap-3 rounded-lg border p-4 ${banner.bg}`}>
      <div className="shrink-0 mt-0.5">{banner.icon}</div>
      <div className="flex-1">
        <p className="text-sm text-gray-700">{banner.text}</p>
        {status === "COMPLETED" && (
          <Link
            href={ROUTES.PORTAL.VERIFICATION_REPORT(verificationId)}
            className="mt-2 inline-flex items-center gap-1.5 text-sm font-medium text-green-700 hover:text-green-900"
          >
            <FileText className="h-4 w-4" />
            View Report
          </Link>
        )}
      </div>
    </div>
  );
}

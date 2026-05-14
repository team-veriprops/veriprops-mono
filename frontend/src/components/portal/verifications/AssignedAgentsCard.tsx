"use client";

import { ShieldCheck, User } from "lucide-react";

interface Agent {
  role: string;
  firstName: string;
  isTrusted: boolean;
}

const ROLE_COLORS: Record<string, string> = {
  FIELD: "bg-blue-100 text-blue-700",
  SURVEYOR: "bg-purple-100 text-purple-700",
  REGISTRY: "bg-green-100 text-green-700",
  LAWYER: "bg-orange-100 text-orange-700",
};

interface Props {
  agents: Agent[];
}

export default function AssignedAgentsCard({ agents }: Props) {
  if (agents.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-400 italic">
        <User className="h-4 w-4" />
        No agents assigned yet.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {agents.map((agent) => (
        <div
          key={`${agent.role}-${agent.firstName}`}
          className="flex items-center gap-3 rounded-lg border border-gray-100 px-3 py-2"
        >
          <span
            className={`text-xs font-semibold px-2 py-0.5 rounded-full ${ROLE_COLORS[agent.role] ?? "bg-gray-100 text-gray-600"}`}
          >
            {agent.role}
          </span>
          <span className="text-sm font-medium text-gray-800">{agent.firstName}</span>
          {agent.isTrusted && (
            <ShieldCheck className="h-4 w-4 text-green-600" aria-label="Trusted Agent" />
          )}
        </div>
      ))}
    </div>
  );
}

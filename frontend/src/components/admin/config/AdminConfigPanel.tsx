"use client";

import { useState } from "react";
import { Button } from "@3rdparty/ui/button";
import { useAdminConfig, useSetConfigMutation } from "../libs/useAdminQueries";
import type { AdminConfig } from "../libs/admin-service";
import { getErrorMessage } from "@lib/utils";
import { Pencil, Check, X } from "lucide-react";

function ConfigRow({ config }: { config: AdminConfig }) {
  const setConfig = useSetConfigMutation();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(config.value);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    try {
      await setConfig.mutateAsync({ key: config.key, value });
      setEditing(false);
      setError(null);
    } catch (e) {
      setError(getErrorMessage(e as Error));
    }
  };

  const handleCancel = () => {
    setValue(config.value);
    setEditing(false);
    setError(null);
  };

  return (
    <div className="flex items-start gap-4 py-3 border-b border-gray-100 last:border-b-0">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 font-mono">{config.key}</p>
        {config.description && (
          <p className="text-xs text-gray-500 mt-0.5">{config.description}</p>
        )}
        {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
      </div>
      <div className="flex items-center gap-2">
        {editing ? (
          <>
            <input
              type="text"
              className="border rounded px-2 py-1 text-sm w-28 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              value={value}
              onChange={(e) => setValue(e.target.value)}
            />
            <button
              onClick={handleSave}
              style={{ cursor: "pointer" }}
              disabled={setConfig.isPending}
              title="Save"
              className="text-green-600 hover:text-green-800"
            >
              <Check className="h-4 w-4" />
            </button>
            <button
              onClick={handleCancel}
              style={{ cursor: "pointer" }}
              title="Cancel"
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="h-4 w-4" />
            </button>
          </>
        ) : (
          <>
            <span className="text-sm text-gray-900 font-medium font-mono">{config.value}</span>
            <button
              onClick={() => setEditing(true)}
              style={{ cursor: "pointer" }}
              title="Edit"
              className="text-gray-400 hover:text-indigo-600"
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default function AdminConfigPanel() {
  const { data, isLoading } = useAdminConfig();
  const configs: AdminConfig[] = (data as any)?.data ?? [];

  return (
    <div className="rounded-lg border border-gray-200 bg-white">
      <div className="px-4 py-3 border-b border-gray-200">
        <h2 className="text-sm font-semibold text-gray-700">System Configuration</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Click the pencil icon to edit a value. Changes take effect immediately.
        </p>
      </div>
      {isLoading ? (
        <div className="py-8 text-center text-gray-400 text-sm">Loading…</div>
      ) : configs.length === 0 ? (
        <div className="py-8 text-center text-gray-400 text-sm">No configuration keys found.</div>
      ) : (
        <div className="px-4">
          {configs.map((c) => (
            <ConfigRow key={c.id} config={c} />
          ))}
        </div>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import {
  useSetSystemConfigMutation,
  useSystemConfigQuery,
} from "@components/admin/config/libs/useSystemConfigQueries";
import { ConfigKey, SystemConfigItem } from "@/types/systemConfig";

/**
 * Admin system-config CRUD (§14/§18.5, D28). Backend owns defaults + coercion; each row is a
 * typed operational knob (dispute window, re-check pricing, agent defence window).
 */
export default function SystemConfigManager() {
  const { data, isLoading, isError } = useSystemConfigQuery();
  return (
    <div className="mx-auto max-w-2xl space-y-4 p-4 sm:p-6">
      <div>
        <h1 className="text-lg font-semibold">System configuration</h1>
        <p className="text-sm text-muted-foreground">Operational settings for re-checks and disputes.</p>
      </div>
      <AsyncStateComponent<SystemConfigItem[]>
        isLoading={isLoading}
        isError={isError}
        data={data}
        loadingText="Loading settings…"
        emptyText="No settings found."
      >
        {(items) => (
          <div className="space-y-3">
            {items.map((item) => (
              <ConfigRow key={item.key} item={item} />
            ))}
          </div>
        )}
      </AsyncStateComponent>
    </div>
  );
}

function ConfigRow({ item }: { item: SystemConfigItem }) {
  const [value, setValue] = useState(String(item.value ?? ""));
  const setConfig = useSetSystemConfigMutation();
  const dirty = value !== String(item.value ?? "");
  const save = () => {
    const num = Number(value);
    if (Number.isNaN(num)) {
      toast.error("Enter a valid number.");
      return;
    }
    setConfig.mutate(
      { key: item.key as ConfigKey, value: num },
      { onSuccess: () => toast.success("Setting saved") },
    );
  };
  return (
    <div className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <p className="text-sm font-medium">{item.key.replace(/_/g, " ")}</p>
        {item.description && <p className="text-xs text-muted-foreground">{item.description}</p>}
      </div>
      <div className="flex items-center gap-2">
        <Input
          className="w-28"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          data-testid={`config-${item.key}`}
        />
        <Button size="sm" disabled={!dirty || setConfig.isPending} onClick={save}>
          Save
        </Button>
      </div>
    </div>
  );
}

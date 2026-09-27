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
import { getErrorMessage } from "@lib/errors";
import { humanizeEnumLabel } from "@lib/utils";

/**
 * Admin system-config CRUD (§14/§18.5, D28). Backend owns defaults, coercion and validation;
 * each row is a typed business knob (dispute window, re-check pricing, commission margin, remote
 * bonus, …). A refused save shows the backend's reason.
 */
export default function SystemConfigManager() {
  const { data, isLoading, isError } = useSystemConfigQuery();
  return (
    <div className="mx-auto max-w-2xl space-y-4 p-4 sm:p-6">
      <div>
        <h1 className="text-lg font-semibold">System configuration</h1>
        <p className="text-sm text-muted-foreground">Business rules that take effect without a redeploy.</p>
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
      {
        onSuccess: () => toast.success("Setting saved"),
        // A refusal (e.g. a remote bonus or minimum margin the commission margin cannot meet)
        // is shown in the backend's words; getErrorMessage keeps a 5xx's text off the screen.
        onError: (err) => toast.error(getErrorMessage(err, "Could not save the setting.")),
      },
    );
  };
  return (
    <div className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <p className="text-sm font-medium">{humanizeEnumLabel(item.key)}</p>
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

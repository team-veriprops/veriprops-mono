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
import { ConfigKey, ConfigUnit, SystemConfigItem } from "@/types/systemConfig";
import { getErrorMessage } from "@lib/errors";
import { humanizeEnumLabel, majorToMinor, minorToMajorText } from "@lib/utils";

/**
 * Admin system-config CRUD (§14/§18.5, D28). Backend owns defaults, coercion and validation;
 * each row is a typed business knob (dispute window, re-check pricing, commission margin, remote
 * bonus, …). The backend declares each key's unit, so money stored in kobo is read and typed in
 * naira here. A refused save shows the backend's reason.
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

/** How a value is shown and typed, by the unit the backend declares for its key. */
const UNIT_INPUT: Record<ConfigUnit, { prefix?: string; suffix?: string }> = {
  [ConfigUnit.MINOR_CURRENCY]: { prefix: "₦" },
  [ConfigUnit.MAJOR_CURRENCY]: { prefix: "₦" },
  [ConfigUnit.PERCENT]: { suffix: "%" },
};

/** The text the input starts from: money stored in kobo is typed in naira. */
function initialText(item: SystemConfigItem): string {
  return item.unit === ConfigUnit.MINOR_CURRENCY ? minorToMajorText(Number(item.value)) : String(item.value ?? "");
}

/** The value to send, in the unit the backend stores; undefined when the text is not valid. */
function toStoredValue(item: SystemConfigItem, text: string): number | undefined {
  if (item.unit === ConfigUnit.MINOR_CURRENCY) return majorToMinor(text);
  const num = Number(text);
  return text.trim() === "" || Number.isNaN(num) ? undefined : num;
}

function ConfigRow({ item }: { item: SystemConfigItem }) {
  const [value, setValue] = useState(() => initialText(item));
  const setConfig = useSetSystemConfigMutation();
  const dirty = value !== initialText(item);
  const affix = item.unit ? UNIT_INPUT[item.unit] : {};
  const save = () => {
    const stored = toStoredValue(item, value);
    if (stored === undefined) {
      toast.error(item.unit === ConfigUnit.MINOR_CURRENCY ? "Enter an amount in naira." : "Enter a valid number.");
      return;
    }
    setConfig.mutate(
      { key: item.key as ConfigKey, value: stored },
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
        {affix.prefix && <span className="text-sm text-muted-foreground">{affix.prefix}</span>}
        <Input
          className="w-28"
          inputMode="decimal"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          aria-label={humanizeEnumLabel(item.key)}
          data-testid={`config-${item.key}`}
        />
        {affix.suffix && <span className="text-sm text-muted-foreground">{affix.suffix}</span>}
        <Button size="sm" disabled={!dirty || setConfig.isPending} onClick={save}>
          Save
        </Button>
      </div>
    </div>
  );
}

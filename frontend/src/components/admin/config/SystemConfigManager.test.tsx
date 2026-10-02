import { afterEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { toast } from "sonner";
import { ConfigKey, ConfigUnit, SystemConfigItem } from "@/types/systemConfig";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@lib/errors", () => ({ getErrorMessage: (_err: unknown, fallback: string) => `safe: ${fallback}` }));

const items: SystemConfigItem[] = [
  { key: ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO, value: 0, unit: ConfigUnit.MINOR_CURRENCY, description: "Flat bonus." },
  { key: ConfigKey.MAX_DISCOUNT_PERCENT, value: 25, unit: ConfigUnit.PERCENT },
  { key: ConfigKey.DISPUTE_WINDOW_DAYS, value: 30 },
];
const mutate = vi.fn();

vi.mock("@components/admin/config/libs/useSystemConfigQueries", () => ({
  useSystemConfigQuery: () => ({ data: items, isLoading: false, isError: false }),
  useSetSystemConfigMutation: () => ({ mutate, isPending: false }),
}));

import SystemConfigManager from "./SystemConfigManager";

let root: Root | null = null;
let host: HTMLElement | null = null;

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = null;
  host = null;
  vi.clearAllMocks();
});

function mount() {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  act(() => root!.render(<SystemConfigManager />));
}

function input(key: ConfigKey) {
  return host!.querySelector<HTMLInputElement>(`[data-testid="config-${key}"]`)!;
}

function typeAndSave(key: ConfigKey, value: string) {
  const field = input(key);
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(field, value);
    field.dispatchEvent(new Event("input", { bubbles: true }));
  });
  const row = field.closest("div")!;
  act(() => row.querySelector<HTMLButtonElement>("button")!.click());
}

describe("SystemConfigManager", () => {
  /**
   * The remote bonus and the minimum margin are refused when they would breach a tier's
   * commission margin (§20.1 / D97); the refusal must reach the admin, through getErrorMessage.
   */
  it("shows a refused save instead of failing silently", () => {
    mutate.mockImplementation((_vars, opts: { onError?: (e: unknown) => void }) => opts.onError?.(new Error("x")));
    mount();
    typeAndSave(ConfigKey.DISPUTE_WINDOW_DAYS, "45");

    expect(mutate).toHaveBeenCalledWith({ key: ConfigKey.DISPUTE_WINDOW_DAYS, value: 45 }, expect.anything());
    expect(toast.error).toHaveBeenCalledWith("safe: Could not save the setting.");
  });

  /** Money the backend stores in kobo is typed in naira: ₦5,000 goes out as 500,000 kobo. */
  it("takes a kobo-stored amount in naira and sends kobo", () => {
    mount();
    typeAndSave(ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO, "5,000");
    expect(mutate).toHaveBeenCalledWith(
      { key: ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO, value: 500_000 }, expect.anything(),
    );
  });

  it("refuses a naira amount it cannot read, without calling the backend", () => {
    mount();
    typeAndSave(ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO, "5.123");
    expect(mutate).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith("Enter an amount in naira.");
  });

  it("marks each value with its declared unit", () => {
    const html = renderToStaticMarkup(<SystemConfigManager />);
    expect(html).toContain("₦");
    expect(html).toContain("%");
  });

  it("labels each key in words, never as the raw key", () => {
    const html = renderToStaticMarkup(<SystemConfigManager />);
    expect(html).toContain("Remote Job Bonus Ngn Kobo");
    expect(html).not.toContain(">remote_job_bonus_ngn_kobo<");
  });
});

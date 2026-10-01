import { afterEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { toast } from "sonner";
import { ConfigKey, SystemConfigItem } from "@/types/systemConfig";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@lib/errors", () => ({ getErrorMessage: (_err: unknown, fallback: string) => `safe: ${fallback}` }));

const items: SystemConfigItem[] = [
  { key: ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO, value: 0, description: "Flat bonus, in kobo." },
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

describe("SystemConfigManager", () => {
  /**
   * The remote bonus and the minimum margin are refused when they would breach a tier's
   * commission margin (§20.1 / D97); the refusal must reach the admin, through getErrorMessage.
   */
  it("shows a refused save instead of failing silently", () => {
    mutate.mockImplementation((_vars, opts: { onError?: (e: unknown) => void }) => opts.onError?.(new Error("x")));
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    act(() => root!.render(<SystemConfigManager />));

    const input = host.querySelector<HTMLInputElement>(`[data-testid="config-${ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO}"]`)!;
    act(() => {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
      setter.call(input, "500000");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    act(() => host!.querySelector<HTMLButtonElement>("button")!.click());

    expect(mutate).toHaveBeenCalledWith(
      { key: ConfigKey.REMOTE_JOB_BONUS_NGN_KOBO, value: 500_000 },
      expect.anything(),
    );
    expect(toast.error).toHaveBeenCalledWith("safe: Could not save the setting.");
  });

  it("labels each key in words, never as the raw key", () => {
    const html = renderToStaticMarkup(<SystemConfigManager />);
    expect(html).toContain("Remote Job Bonus Ngn Kobo");
    expect(html).not.toContain(">remote_job_bonus_ngn_kobo<");
  });
});

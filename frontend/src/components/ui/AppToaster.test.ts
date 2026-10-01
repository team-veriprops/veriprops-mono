import { describe, it, expect } from "vitest";

import { WHATSAPP_WIDGET_CLEARANCE_PX } from "@components/website/WhatsAppWidget";

import { toasterPlacement } from "./AppToaster";

describe("toasterPlacement", () => {
  it("puts a phone's toasts at the top, clear of the form buttons along the bottom", () => {
    expect(toasterPlacement(true)).toEqual({ position: "top-center" });
  });

  it("keeps wider screens in the bottom-right corner, stacked above the WhatsApp widget", () => {
    expect(toasterPlacement(false)).toEqual({
      position: "bottom-right",
      offset: { bottom: WHATSAPP_WIDGET_CLEARANCE_PX },
    });
  });
});

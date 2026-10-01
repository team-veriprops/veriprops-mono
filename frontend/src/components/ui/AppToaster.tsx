"use client";

import type { ToasterProps } from "sonner";

import { Toaster } from "@components/3rdparty/ui/sonner";
import { WHATSAPP_WIDGET_CLEARANCE_PX } from "@components/website/WhatsAppWidget";
import { useIsMobile } from "@hooks/use-mobile";

/**
 * Where toasts appear. On a phone a bottom toast spans the screen's width, exactly where forms put
 * their primary button — a "verified" toast sat over signup's Continue, so a tap meant for the step
 * landed on the toast and nothing advanced. Phones therefore get toasts at the top. Wider screens keep
 * the bottom-right corner, stacked above the WhatsApp widget that holds it.
 */
export function toasterPlacement(isMobile: boolean): Pick<ToasterProps, "position" | "offset"> {
  if (isMobile) return { position: "top-center" };
  return { position: "bottom-right", offset: { bottom: WHATSAPP_WIDGET_CLEARANCE_PX } };
}

export default function AppToaster() {
  return <Toaster {...toasterPlacement(useIsMobile())} />;
}

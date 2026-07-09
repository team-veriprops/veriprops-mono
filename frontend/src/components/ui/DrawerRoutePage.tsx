"use client";

import { ReactNode, useState } from "react";
import { useRouter } from "next/navigation";
import DetailDrawer, { DetailDrawerWidth } from "./DetailDrawer";

interface DrawerRoutePageProps {
  title: string;
  reference: string;
  description?: string;
  /** Where to go when the drawer closes if there is no history to go back to. */
  fallbackHref: string;
  drawerWidth?: DetailDrawerWidth;
  children: ReactNode;
}

/**
 * Presents a deep-linkable detail *route* as a right-side drawer. The drawer is
 * open on mount; closing it navigates back to the originating list (or the
 * fallback when the route was loaded directly). This keeps every detail view a
 * real, refresh-safe URL while rendering it as a drawer for a consistent UX.
 */
export default function DrawerRoutePage({
  title,
  reference,
  description,
  fallbackHref,
  drawerWidth = DetailDrawerWidth.LARGE,
  children,
}: DrawerRoutePageProps) {
  const router = useRouter();
  const [open, setOpen] = useState(true);

  const handleClose = () => {
    setOpen(false);
    // Let the exit animation start, then leave the route.
    window.setTimeout(() => {
      if (window.history.length > 1) {
        router.back();
      } else {
        router.push(fallbackHref);
      }
    }, 200);
  };

  return (
    <DetailDrawer
      open={open}
      onOpenChange={(next) => !next && handleClose()}
      title={title}
      reference={reference}
      description={description}
      drawerWidth={drawerWidth}
    >
      {children}
    </DetailDrawer>
  );
}

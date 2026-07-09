"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@3rdparty/ui/breadcrumb";
import { buildBreadcrumbs } from "./breadcrumb-config";

export default function TopNavBreadcrumb() {
  const pathname = usePathname();
  const crumbs = buildBreadcrumbs(pathname);

  if (crumbs.length === 0) return null;

  return (
    <Breadcrumb>
      <BreadcrumbList>
        {crumbs.map((crumb, index) => (
          <span key={crumb.href} className="inline-flex items-center gap-1.5 sm:gap-2.5">
            {index > 0 && <BreadcrumbSeparator />}
            <BreadcrumbItem>
              {crumb.isCurrentPage ? (
                <BreadcrumbPage className="text-sm font-medium" style={{ color: "var(--brand-navy)" }}>
                  {crumb.label}
                </BreadcrumbPage>
              ) : (
                <BreadcrumbLink asChild>
                  <Link href={crumb.href} className="text-sm" style={{ color: "rgba(0,13,34,0.45)" }}>
                    {crumb.label}
                  </Link>
                </BreadcrumbLink>
              )}
            </BreadcrumbItem>
          </span>
        ))}
      </BreadcrumbList>
    </Breadcrumb>
  );
}

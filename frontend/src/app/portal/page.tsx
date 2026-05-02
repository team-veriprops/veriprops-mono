import { redirect } from "next/navigation";
import { ROUTES } from "@lib/routes";

export default function PortalPage() {
  redirect(ROUTES.PORTAL.DASHBOARD);
}

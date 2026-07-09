import { ROUTES } from "@/lib/routes";
import { redirect } from "next/navigation";

export default function PortalPage() {
  redirect(ROUTES.ADMIN.DASHBOARD);
}

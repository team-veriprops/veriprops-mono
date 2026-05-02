import { redirect } from "next/navigation";
import { ROUTES } from "@lib/routes";

export default function AgentsPage() {
  redirect(ROUTES.AGENT.ONBOARDING);
}

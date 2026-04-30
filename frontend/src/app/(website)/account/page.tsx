import { redirect } from "next/navigation";
import { ROUTES } from "@lib/routes";

export default function AccountIndex() {
  redirect(ROUTES.ACCOUNT.SECURITY);
}

import { ShieldAlert } from "lucide-react";
import StatusPage from "@components/ui/StatusPage";
import ForbiddenActions from "@components/website/ForbiddenActions";

/** Where `FetchHttpClient` sends any 403 — a session that lacks permission for what it asked. */
export default function ForbiddenPage() {
  return (
    <StatusPage
      code={403}
      eyebrow="Restricted area"
      icon={ShieldAlert}
      title="This page isn’t open to your account"
      message="Access on Veriprops is granted by role and by case, so every report and document stays with the people entitled to see it. If you think you should have access, contact support and we’ll look into it."
      actions={<ForbiddenActions />}
    />
  );
}

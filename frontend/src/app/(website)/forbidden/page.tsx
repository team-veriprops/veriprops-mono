import StatusPage from "@components/ui/StatusPage";
import ForbiddenActions from "@components/website/ForbiddenActions";

/** Where `FetchHttpClient` sends any 403 — a session that lacks permission for what it asked. */
export default function ForbiddenPage() {
  return (
    <StatusPage
      code={403}
      title="You don’t have access to this page"
      message="Your account doesn’t have permission to view it. If you think this is a mistake, contact support."
      actions={<ForbiddenActions />}
    />
  );
}

import { Suspense } from "react";
import AdminMessagesTabs from "@components/chat/AdminMessagesTabs";

export default function AdminMessagesPage() {
  // The active tab is read from `?tab=` (useSearchParams needs a Suspense boundary).
  return (
    <Suspense>
      <AdminMessagesTabs />
    </Suspense>
  );
}

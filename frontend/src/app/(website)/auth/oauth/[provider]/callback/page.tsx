import { Metadata } from "next";
import { Suspense } from "react";
import OAuthCallbackContainer from "@components/website/auth/oauth/OAuthCallbackContainer";

export const metadata: Metadata = {
  title: "Signing you in",
  robots: "noindex, follow",
};

// The container reads the query string (useSearchParams), which needs a Suspense boundary.
export default async function OAuthCallbackPage({
  params,
}: {
  params: Promise<{ provider: string }>;
}) {
  const { provider } = await params;
  return (
    <Suspense>
      <OAuthCallbackContainer provider={provider} />
    </Suspense>
  );
}

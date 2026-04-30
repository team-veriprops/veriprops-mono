import { Metadata } from "next";
import OAuthCallbackContainer from "@components/website/auth/oauth/OAuthCallbackContainer";

export const metadata: Metadata = {
  title: "Signing you in",
  robots: "noindex, follow",
};

export default async function OAuthCallbackPage({
  params,
}: {
  params: Promise<{ provider: string }>;
}) {
  const { provider } = await params;
  return <OAuthCallbackContainer provider={provider} />;
}

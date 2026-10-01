import { Metadata } from "next";
import { Suspense } from "react";
import AuthGateContainer from "@components/website/auth/AuthGateContainer";

export const metadata: Metadata = {
  title: "Continue to Veriprops",
  description: "Sign in or create an account to start a property verification.",
  robots: "noindex, follow",
};

// The container reads the query string (useSearchParams), which needs a Suspense boundary.
export default function AuthGatePage() {
  return (
    <Suspense>
      <AuthGateContainer />
    </Suspense>
  );
}

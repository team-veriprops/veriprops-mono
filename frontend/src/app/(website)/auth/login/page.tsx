import { Metadata } from "next";
import { Suspense } from "react";
import LoginContainer from "@components/website/auth/login/LoginContainer";

export const metadata: Metadata = {
  title: "Sign in to Veriprops",
  description: "Sign in to your Veriprops account.",
  robots: "noindex, follow",
};

// The container reads the query string (useSearchParams), which needs a Suspense boundary.
export default function LoginPage() {
  return (
    <Suspense>
      <LoginContainer />
    </Suspense>
  );
}

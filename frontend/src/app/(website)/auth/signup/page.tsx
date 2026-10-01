import { Metadata } from "next";
import { Suspense } from "react";
import SignupContainer from "@components/website/auth/signup/SignupContainer";

export const metadata: Metadata = {
  title: "Create your Veriprops account",
  description: "Create a Veriprops account to start a property verification.",
  robots: "noindex, follow",
};

// The container reads the query string (useSearchParams), which needs a Suspense boundary.
export default function SignupPage() {
  return (
    <Suspense>
      <SignupContainer />
    </Suspense>
  );
}

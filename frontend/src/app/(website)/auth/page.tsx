import { Metadata } from "next";
import AuthGateContainer from "@components/website/auth/AuthGateContainer";

export const metadata: Metadata = {
  title: "Continue to Veriprops",
  description: "Sign in or create an account to start a property verification.",
  robots: "noindex, follow",
};

export default function AuthGatePage() {
  return <AuthGateContainer />;
}

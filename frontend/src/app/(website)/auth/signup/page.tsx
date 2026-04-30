import { Metadata } from "next";
import SignupContainer from "@components/website/auth/signup/SignupContainer";

export const metadata: Metadata = {
  title: "Create your Veriprops account",
  description: "Create a Veriprops account to start a property verification.",
  robots: "noindex, follow",
};

export default function SignupPage() {
  return <SignupContainer />;
}

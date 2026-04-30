import { Metadata } from "next";
import LoginContainer from "@components/website/auth/login/LoginContainer";

export const metadata: Metadata = {
  title: "Sign in to Veriprops",
  description: "Sign in to your Veriprops account.",
  robots: "noindex, follow",
};

export default function LoginPage() {
  return <LoginContainer />;
}

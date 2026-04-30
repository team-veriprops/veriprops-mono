import { Metadata } from "next";
import ForgotPasswordContainer from "@components/website/auth/password/ForgotPasswordContainer";

export const metadata: Metadata = {
  title: "Reset your Veriprops password",
  robots: "noindex, follow",
};

export default function ForgotPasswordPage() {
  return <ForgotPasswordContainer />;
}

import { Metadata } from "next";
import SetPasswordContainer from "@components/website/auth/password/SetPasswordContainer";

export const metadata: Metadata = {
  title: "Set a password",
  robots: "noindex, follow",
};

export default function SetPasswordPage() {
  return <SetPasswordContainer />;
}

import { Metadata } from "next";
import ResetPasswordContainer from "@components/website/auth/password/ResetPasswordContainer";

export const metadata: Metadata = {
  title: "Reset your Veriprops password",
  robots: "noindex, follow",
};

export default async function ResetPasswordPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <ResetPasswordContainer token={token} />;
}

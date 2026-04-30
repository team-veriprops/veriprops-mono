import { Metadata } from "next";
import SecurityActivityContainer from "@components/account/SecurityActivityContainer";

export const metadata: Metadata = {
  title: "Security activity",
  robots: "noindex, follow",
};

export default function SecurityActivityPage() {
  return <SecurityActivityContainer />;
}

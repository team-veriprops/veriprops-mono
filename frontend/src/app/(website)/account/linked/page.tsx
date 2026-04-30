import { Metadata } from "next";
import LinkedAccountsContainer from "@components/account/LinkedAccountsContainer";

export const metadata: Metadata = {
  title: "Linked accounts",
  robots: "noindex, follow",
};

export default function LinkedAccountsPage() {
  return <LinkedAccountsContainer />;
}

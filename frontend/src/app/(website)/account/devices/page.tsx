import { Metadata } from "next";
import DevicesContainer from "@components/account/DevicesContainer";

export const metadata: Metadata = {
  title: "Connected devices",
  robots: "noindex, follow",
};

export default function DevicesPage() {
  return <DevicesContainer />;
}

import { Metadata, Viewport } from "next";
import "@app/globals.css";
import { ClientWrapperProvider } from "@/providers/client-wrapper";

export const metadata: Metadata = {
  metadataBase: new URL("https://veriprops.ng"),
  title: "Veriprops - Verify Property Ownership & Land Size in Nigeria | Stop Scams Before You Pay",
  description: "Independent property verification for Nigerian buyers. We validate ownership, survey plans, land size, disputes, and real-world accuracy from any third-party listing or property claim. Verify before you pay.",
  keywords: [
    "Nigeria property verification",
    "land ownership verification Nigeria",
    "survey plan validation Nigeria",
    "land size accuracy check Nigeria",
    "avoid property scams Nigeria",
    "real estate due diligence Nigeria",
    "verify land before buying Nigeria",
    "building approval verification Nigeria",
    "property fraud prevention Nigeria",
    "third-party property listing verification Nigeria"
  ],
  icons: {
    icon: "/favicon.png",
  },
  authors: [{ name: "Veriprops" }],
  robots: "index, follow",
  openGraph: {
    title: "Veriprops | Verify Before You Pay",
    description: "We validate property ownership, survey plans, land size accuracy and disputes from any listing site or property claim. Nigeria’s trusted Property Truth Layer.",
    type: "website",
    siteName: "veriprops.ng",
    url: "https://veriprops.ng",
    locale: "en_NG",
    images: [{ url: "/og-image.png" }],
  },
  twitter: {
    title: "Veriprops | Nigeria’s Property Truth Layer",
    description: "Stop property scams. Verify ownership, land size, survey plans and disputes before payment.",
    card: "summary_large_image",
    site: "@veriprops",
    images: [{ url: "/og-image.png" }],
  },
  alternates: {
    canonical: "/"
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};


export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="">
        <ClientWrapperProvider>{children}</ClientWrapperProvider>
      </body>
    </html>
  );
}

import { Metadata, Viewport } from "next";
import "@app/globals.css";
import { ClientWrapperProvider } from "@/providers/client-wrapper";
import { buildMetadata } from "@lib/seo";

export const metadata: Metadata = {
  // Site-wide default; pages override title/description/canonical via buildMetadata.
  ...buildMetadata({
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
      "third-party property listing verification Nigeria",
    ],
  }),
  icons: {
    icon: "/favicon/favicon_ico_16x16.png",
  },
  authors: [{ name: "Veriprops" }],
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

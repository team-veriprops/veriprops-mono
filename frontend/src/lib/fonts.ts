import { Inter, Manrope } from "next/font/google";

/**
 * The app's typefaces, self-hosted by next/font: the files are downloaded at build time and served
 * from this origin, so no page waits on a third-party font host at runtime. Each font exposes a CSS
 * variable that `styles/theme.css` maps onto the `--font-sans` / `--font-display` design tokens.
 */
export const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-inter",
});

export const manrope = Manrope({
  subsets: ["latin"],
  weight: ["400", "600", "700", "800"],
  display: "swap",
  variable: "--font-manrope",
});

/** Class names that define both font variables; applied once on <html>. */
export const fontVariables = `${inter.variable} ${manrope.variable}`;

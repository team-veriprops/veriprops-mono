import { motion } from "framer-motion";
import { Shield } from "lucide-react";
import Link from "next/link";
import { ROUTES } from "@lib/routes";

interface BrandLogoProps {
  /** "dark" for light surfaces (navy tile), "light" for navy surfaces (viridian tile). */
  variant?: "dark" | "light";
  /**
   * "default" — full lockup (tile + wordmark + tagline), e.g. sidebar/landing.
   * "sm"      — tile + wordmark, no tagline, e.g. compact mobile headers.
   * "compact" — tile only, e.g. the collapsed sidebar rail.
   */
  size?: "default" | "sm" | "compact";
}

export default function BrandLogo({
  variant = "dark",
  size = "default",
}: BrandLogoProps) {
  const isLight = variant === "light";
  const tileOnly = size === "compact";
  const showTagline = size === "default";

  // On navy surfaces the navy tile disappears — switch to viridian with a soft ring.
  const tileClasses = isLight
    ? "bg-[var(--brand-viridian)] ring-1 ring-white/20"
    : "bg-[var(--brand-navy)]";

  const tileSize = size === "sm" ? "h-8 w-8 rounded-lg" : "h-10 w-10 rounded-xl";
  const shieldSize = size === "sm" ? "h-4 w-4" : "h-5 w-5";

  return (
    <Link href={ROUTES.HOME} className="inline-block" aria-label="Veriprops home">
      <motion.div
        className="flex items-center gap-2"
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      >
        <div className={`flex items-center justify-center ${tileSize} ${tileClasses}`}>
          <Shield className={`${shieldSize} text-white`} strokeWidth={2} />
        </div>

        {!tileOnly && (
          <div>
            <span
              className={`font-bold ${size === "sm" ? "text-lg" : "text-xl"} ${
                isLight ? "text-white" : "text-foreground"
              }`}
            >
              veriprops
            </span>

            {showTagline && (
              <p
                className={`-mt-1.5 text-sm ${
                  isLight ? "text-white/70" : "text-muted-foreground"
                }`}
              >
                verified properties
              </p>
            )}
          </div>
        )}
      </motion.div>
    </Link>
  );
}

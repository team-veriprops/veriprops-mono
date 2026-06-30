import { motion } from "framer-motion";
import { Shield } from "lucide-react";
import Link from "next/link";
import { ROUTES } from "@lib/routes";

interface BrandLogoProps {
  variant?: "dark" | "light";
}

export default function BrandLogo({
  variant = "dark",
}: BrandLogoProps) {
  const isLight = variant === "light";

  return (
    <Link href={ROUTES.HOME} className="inline-block">
      <motion.div
        className="flex items-center space-x-2"
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      >
        <div 
        className="flex h-10 w-10 items-center justify-center rounded-xl"
        style={{ backgroundColor: "var(--brand-navy)", borderColor: "rgba(196,198,207,0.4)" }}>
          <Shield className="h-5 w-5 text-primary-foreground" />
        </div>

        <div>
          <span
            className={`text-xl font-bold ${
              isLight ? "text-white" : "text-foreground"
            }`}
          >
            veriprops
          </span>

          <p
            className={`-mt-1.5 text-sm ${
              isLight ? "text-white/80" : "text-muted-foreground"
            }`}
          >
            verified properties
          </p>
        </div>
      </motion.div>
    </Link>
  );
}

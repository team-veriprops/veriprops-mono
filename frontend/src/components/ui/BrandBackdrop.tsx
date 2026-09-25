import { cn } from "@lib/utils";

interface BrandBackdropProps {
  /** "light" on white/surface sections (navy dots), "dark" on navy sections (white dots). */
  tone?: "light" | "dark";
  /** Adds the soft viridian glow in the top-right corner (light tone only) that the hero uses. */
  glow?: boolean;
}

const DOT_GRID: Record<NonNullable<BrandBackdropProps["tone"]>, string> = {
  light: "bg-[radial-gradient(circle_at_1px_1px,rgba(0,13,34,0.04)_1px,transparent_0)]",
  dark: "bg-[radial-gradient(circle_at_1px_1px,rgba(255,255,255,0.04)_1px,transparent_0)]",
};

/**
 * The brand's decorative atmosphere: the faint 40px dot grid behind marketing sections and
 * full-page dead ends. Purely visual, so it is hidden from assistive tech and never takes clicks.
 * The parent must be `relative` (and usually `overflow-hidden`).
 */
export default function BrandBackdrop({ tone = "light", glow = false }: BrandBackdropProps) {
  return (
    <>
      <div aria-hidden className={cn("absolute inset-0 pointer-events-none bg-size-[40px_40px]", DOT_GRID[tone])} />
      {glow && tone === "light" && (
        <div
          aria-hidden
          className="absolute -top-32 -right-32 w-150 h-150 rounded-full pointer-events-none bg-[radial-gradient(circle,rgba(63,102,83,0.06)_0%,transparent_70%)]"
        />
      )}
    </>
  );
}

import { Button } from "@components/3rdparty/ui/button";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { CopyText } from "./CopyText";
import { ReactNode } from "react";
import MobileNavigationBottomPadding from "./MobileNavigationBottomPadding";
import { useBodyOverflowHidden } from "@hooks/useBodyOverflowHidden";
import { cn } from "@lib/utils";

export enum DetailDrawerWidth {
  SMALL = "600px",
  MEDIUM = "850px",
  LARGE = "1200px",
}
interface DetailDrawerProps {
  title: string;
  reference: string;
  description?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: ReactNode;
  drawerWidth?: DetailDrawerWidth;
}
export default function DetailDrawer({
  title,
  reference,
  description,
  open,
  onOpenChange,
  children,
  drawerWidth = DetailDrawerWidth.SMALL,
}: DetailDrawerProps) {
  // Lock body scroll when modal is open
  useBodyOverflowHidden(open);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => onOpenChange(open)}
            className="fixed inset-0 w-full h-full bg-background/80 backdrop-blur-sm z-50"
          />

          {/* Drawer */}
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className={cn(
              "fixed right-0 top-0 h-full w-full bg-card border-l border-border shadow-2xl z-50 overflow-y-auto",
              drawerWidth === DetailDrawerWidth.SMALL && "sm:max-w-150",
              drawerWidth === DetailDrawerWidth.MEDIUM && "sm:max-w-212.5",
              drawerWidth === DetailDrawerWidth.LARGE && "sm:max-w-300"
            )}
            //   className={`fixed right-0 top-0 h-full w-full sm:max-w-none bg-card border-l border-border shadow-2xl z-50 overflow-y-auto`}
            // style={{ maxWidth: drawerWidth }}
          >
            <div className="sticky top-0 bg-card/95 backdrop-blur-sm border-b border-border z-10 p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold capitalize">{title}</h2>
                  <CopyText text={reference} />
                  {description && <p className=" text-muted-foreground">{description}</p>}
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => onOpenChange(open)}
                >
                  <X className="h-5 w-5" />
                </Button>
              </div>
            </div>
            {children}

            <MobileNavigationBottomPadding />
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

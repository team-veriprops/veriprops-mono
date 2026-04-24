import { motion } from "framer-motion";
import { Shield } from "lucide-react";
import Link from "next/link";

export default function BrandLogo() {
  return (
    // <div>
    //   <h3 className="font-semibold text-lg">veriprops</h3>
    //   <p className=" text-sm -mt-1.5 text-muted-foreground">verified properties</p>
    // </div>
    <>
            <Link href="/" className="inline-block">
            <motion.div 
              className="flex items-center space-x-2"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
              <Shield className="w-5 h-5 text-primary-foreground" />
            </div>
              {/* <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                <span className="text-primary-foreground font-bold text-sm">V</span>
              </div> */}
              <div>
                <span className="text-xl font-bold text-foreground">veriprops</span>
                <p className=" text-sm -mt-1.5 text-muted-foreground">verified properties</p>
              </div>
            </motion.div>
          </Link>
    </>
  );
}


  //  <div className="flex items-center gap-3">
  //           <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
  //             <Shield className="w-5 h-5 text-primary-foreground" />
  //           </div>
  //           <span className="font-display font-bold text-xl text-foreground">Veriprops</span>
  //         </div>
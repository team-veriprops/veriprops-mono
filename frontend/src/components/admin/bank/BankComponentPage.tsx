"use client";

import { motion } from "framer-motion";
import { PageDetails } from "@/types/models";
import PageHeader from "@components/ui/PageHeader";
import BankTable from "./BankTable";

export default function BankComponentPage({ title, description }: PageDetails) {


  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="space-y-8"
    >
      {/* Header */}
      <PageHeader title={title} description={description} />
        <BankTable />
    </motion.div>
  );
}

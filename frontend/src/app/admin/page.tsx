import AdminDashboard from "@components/admin/AdminDashboard";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard | Veriprops Admin",
};

export default function AdminPage() {
  return <AdminDashboard />;
}

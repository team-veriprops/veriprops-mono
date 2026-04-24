import BankComponentPage from "@components/admin/bank/BankComponentPage";
import { Metadata } from "next";

const title = "Banks";
const description =
  "Manage Banks";

export const metadata: Metadata = {
  title: `${title} | Veriprops`,
  description: description,
};

export default function AdminPage() {

  return (
    <BankComponentPage title={title} description={description}  />
  );
}

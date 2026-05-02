import TeamManagement from "@components/admin/team/TeamManagement";

export const metadata = {
  title: "Admin team — Veriprops",
};

export default function AdminTeamPage() {
  return (
    <div className="max-w-5xl mx-auto px-4 py-10">
      <TeamManagement />
    </div>
  );
}

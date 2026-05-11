import TaskReviewPageClient from "./TaskReviewPageClient";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Task Review | Veriprops Admin",
};

interface Props {
  params: { taskId: string };
  searchParams: { vid?: string };
}

export default function TaskReviewPage({ params, searchParams }: Props) {
  return (
    <div className="p-6">
      <TaskReviewPageClient
        taskId={params.taskId}
        vid={searchParams.vid ?? ""}
      />
    </div>
  );
}

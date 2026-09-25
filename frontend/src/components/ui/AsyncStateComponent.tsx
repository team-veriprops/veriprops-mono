import { ReactNode } from "react";
import { Loader2 } from "lucide-react";

interface AsyncStateProps<T> {
  isLoading: boolean;
  isError: boolean;
  data?: T | null;
  loadingText?: string;
  errorText?: string;
  emptyText?: string;
  children: (data: T) => ReactNode;
}

export function AsyncStateComponent<T>({
  isLoading,
  isError,
  data,
  loadingText = "Loading...",
  errorText = "Something went wrong, please try again later.",
  emptyText = "No records found.",
  children,
}: AsyncStateProps<T>) {
  // Muted text here is `gray-600`, not `gray-500`: 500 is 4.39:1 on the app's `#f3f4f5` surfaces
  // and fails WCAG AA. This component states every surface's loading, error and empty state, so a
  // failure here is a failure on all of them.
  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-6 text-gray-600">
        <Loader2 className="h-5 w-5 mr-2 animate-spin" />
        {loadingText}
      </div>
    );
  }

  if (isError) {
    return <div className="flex p-6 items-center justify-center text-destructive">{errorText}</div>;
  }

  if (!data) {
    return <div className="flex p-6 items-center justify-center text-gray-600">{emptyText}</div>;
  }

  return <>{children(data)}</>;
}

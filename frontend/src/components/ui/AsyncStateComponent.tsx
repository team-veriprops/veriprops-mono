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
  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-6 text-gray-500">
        <Loader2 className="h-5 w-5 mr-2 animate-spin" />
        {loadingText}
      </div>
    );
  }

  if (isError) {
    return <div className="flex p-6 items-center justify-center text-red-500">{errorText}</div>;
  }

  if (!data) {
    return <div className="flex p-6 items-center justify-center text-gray-500">{emptyText}</div>;
  }

  return <>{children(data)}</>;
}

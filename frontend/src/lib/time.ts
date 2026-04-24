import { formatDistanceToNow, differenceInDays, format } from "date-fns";

export const formatRelativeTime = (dateString: string): string => {
  try {
    return formatDistanceToNow(new Date(dateString), { addSuffix: true });
  } catch {
    return "recently";
  }
};

export const formatDate = (dateStr: string) => {
  // console.log("formatDate(dateStr: string): ", dateStr)
  if(!dateStr){
    return ""
  }

  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

export const toTimeAgo = (date: Date | string) => {
  if (!date) return "recently";

  const seconds = Math.floor((Date.now() - new Date(date!).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
};

export const getDaysUntil = (dateString: string): number => {
  try {
    return differenceInDays(new Date(dateString), new Date());
  } catch {
    return 0;
  }
};

export const formatCountdown = (dateString: string): string => {
  const days = getDaysUntil(dateString);
  if (days < 0) return "Released";
  if (days === 0) return "Today";
  if (days === 1) return "1 day";
  return `${days} days`;
};

export const nowISO = (): string => {
  return new Date().toISOString();
};

export const timeDiffHours = (fromDate: string, toDate: string = nowISO()): number => {
  const from = new Date(fromDate).getTime();
  const to = new Date(toDate).getTime();
  return Math.abs((to - from) / (1000 * 60 * 60));
};

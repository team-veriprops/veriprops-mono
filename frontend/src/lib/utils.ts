import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { redirect } from "next/navigation";
import { getFxRate, Measurement, Money, TransactionCurrency } from "@/types/models";
import { HttpError } from "./FetchHttpClient";


/**
 * Combines multiple class name values into a single string,
 * and intelligently merges Tailwind CSS classes to avoid conflicts.
 * It’s especially useful when:
     1. You want to conditionally join class names
     2. You're using tailwind-variants or clsx
     3. You want to merge conflicting Tailwind utilities properly
 *
 * @example
 * cn('bg-white', 'text-black', conditional && 'opacity-50')
 * // → "bg-white text-black opacity-50" (if conditional is truthy)
 *
 * @example
 * cn('p-2', 'p-4') // → "p-4" (twMerge resolves the conflict)
 *
 * @param {...ClassValue[]} inputs - A list of class values, which can be strings, objects, arrays, or conditionals.
 * @returns {string} - A single, space-separated, conflict-resolved string of class names.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// export const isActivePath = (path: string, pathname: string) => {
//   return pathname.startsWith(path)
// };

export function isActivePath(
  key: string,
  pathname: string,
  other_links: string[]
): boolean {
  // 1. Check direct match (pathname starts with key)
  if (pathname.startsWith(key)) {
    return true;
  }

  // 2. Check other_links match
  const keyLast = key.substring(key.lastIndexOf("/")); // e.g. "/lands"
  return other_links.some((link) => {
    const linkLast = link.substring(link.lastIndexOf("/")); // e.g. "/lands"
    // console.log("pathname: ", pathname, ", key: ", key, ", link: ", link, ", linkLast: ", linkLast, ", keyLast: ", keyLast )
    return pathname.startsWith(link) && linkLast === keyLast;
  });
}

export const convertMoney = (money: Money | null): Money | null => {
  if(!money){
    return null
  }

  if (!(money instanceof Money)) {
    money = Money.from(money);
  }
  return money;
};

export const formatMoney = (money: Money | null) => {
  if(!money){
    return "error"
  }
  
  money = convertMoney(money);

  if (money)
    return new Intl.NumberFormat("en-NG", {
      style: "currency",
      currency: money.getCurrency(),
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(money.getValue());
};

export const formatMoneyFxAware = (currency: TransactionCurrency, money: Money | null) => {
    const formattedMoney = convertMoney(money)
    const fxRateAwareMoney = currency === TransactionCurrency.NGN ? formattedMoney : Money.from({value: (formattedMoney?.getValue() ?? 1) * getFxRate(currency), currency: currency});

    return formatMoney(fxRateAwareMoney);
};

export const formatMeasurement = (measurement: Measurement | undefined) => {
  // console.log("formatMeasurement(measurement: Measurement): ", measurement)

  if(!measurement){
    return ""
  }

  return measurement.value + " " + measurement.unit;
};

const formatCoordinates = (value: number, isLat: boolean) => {
  const dir = isLat ? (value >= 0 ? "N" : "S") : (value >= 0 ? "E" : "W");
  return `${Math.abs(value).toFixed(4)}° ${dir}`;
};
export const formatLocationCoordinates = (coordinates: {lat: number, lng: number} | undefined) => {
  // console.log("formatMeasurement(measurement: Measurement): ", measurement)

  if(!coordinates){
    return ""
  }

  return `${formatCoordinates(coordinates.lat, true)}, ${formatCoordinates(coordinates.lng, false)}`;
};

export const onLogoutRedirect = () => {
  redirect("/");
};

export const getSearchQuery = (searchKey: string, searchParams: string) => {
  // Gets search query from browser

  const params = new URLSearchParams(searchParams);
  const query = params.get(searchKey!)?.toLowerCase() ?? "";

  return query;
};

export function toQueryParams(payload: object): string {
  const params = new URLSearchParams();

  Object.entries(payload).forEach(([key, value]) => {
    if (value === undefined || value === null) return;

    if (Array.isArray(value)) {
      // append each array item separately
      value.forEach((v) => params.append(key, String(v)));
    } else if (typeof value === "object") {
      // stringify objects (e.g. ranges, filters)
      params.append(key, JSON.stringify(value));
    } else {
      params.append(key, String(value));
    }
  });

  return params.toString();
}

export const stringifyFilters = (filters: Record<string, unknown>) => {
  if (!filters) return {};
  return Object.fromEntries(
    Object.entries(filters).map(([key, value]) => [
      key,
      typeof value === "object" ? JSON.stringify(value) : String(value),
    ])
  );
};

export const handleToggleSort = (
  key: string,
  orderBy: string,
  updateOrderByInStore: (orderBy: string) => void
) => {
  let newOrderBy: string;

  if (orderBy) {
    const [sortKey, currentOrder = "asc"] = orderBy.split(" ");

    if (sortKey === key) {
      const nextOrder = currentOrder === "asc" ? "desc" : "asc";
      newOrderBy = `${sortKey} ${nextOrder}`;
    } else {
      newOrderBy = `${key} asc`;
    }
  } else {
    newOrderBy = `${key} asc`;
  }

  updateOrderByInStore(newOrderBy);
};

export async function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard && window.isSecureContext) {
    return await navigator.clipboard.writeText(text);
  } else {
    // fallback for older browsers
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed"; // avoid scrolling to bottom
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
    return Promise.resolve();
  }
}

export function buildPath(
  template: string,
  params: Record<string, string>
): string {
  return template.replace(/\{(\w+)\}/g, (_, key) => params[key] ?? "");
}

export function buildReferralLink(referralCode: string) {
  return `${window.location.origin}/signup?ref=${referralCode}`;
}

export const getStatusBadgeColor = (status: string): string => {
  const colors: Record<string, string> = {
    pending: "bg-muted text-muted-foreground",
    inProgress: "bg-warning/10 text-warning dark:bg-warning/20",
    completed: "bg-success/10 text-success dark:bg-success/20",
    blocked: "bg-danger/10 text-danger dark:bg-danger/20",
    verified: "bg-success/10 text-success dark:bg-success/20",
    flagged: "bg-danger/10 text-danger dark:bg-danger/20",
    active: "bg-danger/10 text-danger dark:bg-danger/20",
    under_review: "bg-warning/10 text-warning dark:bg-warning/20",
    resolved: "bg-success/10 text-success dark:bg-success/20",
    paid: "bg-success/10 text-success dark:bg-success/20",
    overdue: "bg-danger/10 text-danger dark:bg-danger/20"
  };
  return colors[status] || "bg-muted text-muted-foreground";
};

// export function isMobileBrowser(): boolean {
//   return (
//     typeof navigator !== 'undefined' &&
//     /Android|iPhone|iPad|iPod|Opera Mini|IEMobile|Mobile/i.test(
//       navigator.userAgent
//     )
//   );
// }

export function isMobileBrowser(): boolean {
  if (typeof navigator === 'undefined') return false

  const ua = navigator.userAgent

  const isMobileUA =
    /Android|iPhone|iPad|iPod|Opera Mini|IEMobile|Mobile/i.test(ua)

  // Covers modern iPads that pretend to be desktop Safari
  const isTouchDevice =
    'maxTouchPoints' in navigator && navigator.maxTouchPoints > 1

  return isMobileUA || isTouchDevice
}

function normalizeBase64(input: string): string {
  let base64 = input.replace(/-/g, '+').replace(/_/g, '/');

  // Pad with '=' if needed
  const pad = base64.length % 4;
  if (pad) {
    base64 += '='.repeat(4 - pad);
  }

  return base64;
}

export function base64UrlToString(input: string): string {
  if(!input){
    return ""
  }
  
  const base64 = normalizeBase64(input);

  // Server
  if (typeof window === 'undefined') {
    return Buffer.from(base64, 'base64').toString('utf-8');
  }

  // Client (UTF-8 safe)
  const binary = window.atob(base64);
  const bytes = Uint8Array.from(binary, c => c.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

export function capitalizeFirst(str: string) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

export function getErrorMessage(error: Error, defaultMessage: string): string {
  return (
    error?.message || defaultMessage ||
    "Something went wrong"
  );
}
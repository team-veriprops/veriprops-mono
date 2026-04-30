import { TransactionCurrency } from "@/types/models";

/**
 * Reference data for residence country / timezone / currency selection.
 * Phase 2 onboarding uses these to (a) suggest a sensible timezone given country,
 * and (b) suggest a sensible currency. Lists are intentionally a curated subset
 * of common diaspora origins; backend can replace with full IANA data later.
 */

export interface CountryInfo {
  code: string;            // ISO 3166-1 alpha-2
  name: string;
  defaultTimezone: string; // IANA tz
  defaultCurrency: TransactionCurrency;
  flag: string;
}

const flagFor = (cc: string): string =>
  String.fromCodePoint(...cc.toUpperCase().split("").map((c) => 127397 + c.charCodeAt(0)));

const raw: Omit<CountryInfo, "flag">[] = [
  { code: "NG", name: "Nigeria",          defaultTimezone: "Africa/Lagos",        defaultCurrency: TransactionCurrency.NGN },
  { code: "GB", name: "United Kingdom",   defaultTimezone: "Europe/London",       defaultCurrency: TransactionCurrency.GBP },
  { code: "US", name: "United States",    defaultTimezone: "America/New_York",    defaultCurrency: TransactionCurrency.USD },
  { code: "CA", name: "Canada",           defaultTimezone: "America/Toronto",     defaultCurrency: TransactionCurrency.USD },
  { code: "DE", name: "Germany",          defaultTimezone: "Europe/Berlin",       defaultCurrency: TransactionCurrency.EUR },
  { code: "FR", name: "France",           defaultTimezone: "Europe/Paris",        defaultCurrency: TransactionCurrency.EUR },
  { code: "IE", name: "Ireland",          defaultTimezone: "Europe/Dublin",       defaultCurrency: TransactionCurrency.EUR },
  { code: "IT", name: "Italy",            defaultTimezone: "Europe/Rome",         defaultCurrency: TransactionCurrency.EUR },
  { code: "ES", name: "Spain",            defaultTimezone: "Europe/Madrid",       defaultCurrency: TransactionCurrency.EUR },
  { code: "NL", name: "Netherlands",      defaultTimezone: "Europe/Amsterdam",    defaultCurrency: TransactionCurrency.EUR },
  { code: "BE", name: "Belgium",          defaultTimezone: "Europe/Brussels",     defaultCurrency: TransactionCurrency.EUR },
  { code: "CH", name: "Switzerland",      defaultTimezone: "Europe/Zurich",       defaultCurrency: TransactionCurrency.EUR },
  { code: "AT", name: "Austria",          defaultTimezone: "Europe/Vienna",       defaultCurrency: TransactionCurrency.EUR },
  { code: "SE", name: "Sweden",           defaultTimezone: "Europe/Stockholm",    defaultCurrency: TransactionCurrency.EUR },
  { code: "NO", name: "Norway",           defaultTimezone: "Europe/Oslo",         defaultCurrency: TransactionCurrency.EUR },
  { code: "DK", name: "Denmark",          defaultTimezone: "Europe/Copenhagen",   defaultCurrency: TransactionCurrency.EUR },
  { code: "FI", name: "Finland",          defaultTimezone: "Europe/Helsinki",     defaultCurrency: TransactionCurrency.EUR },
  { code: "AU", name: "Australia",        defaultTimezone: "Australia/Sydney",    defaultCurrency: TransactionCurrency.USD },
  { code: "NZ", name: "New Zealand",      defaultTimezone: "Pacific/Auckland",    defaultCurrency: TransactionCurrency.USD },
  { code: "AE", name: "United Arab Emirates", defaultTimezone: "Asia/Dubai",       defaultCurrency: TransactionCurrency.USD },
  { code: "SA", name: "Saudi Arabia",     defaultTimezone: "Asia/Riyadh",         defaultCurrency: TransactionCurrency.USD },
  { code: "QA", name: "Qatar",            defaultTimezone: "Asia/Qatar",          defaultCurrency: TransactionCurrency.USD },
  { code: "ZA", name: "South Africa",     defaultTimezone: "Africa/Johannesburg", defaultCurrency: TransactionCurrency.USD },
  { code: "KE", name: "Kenya",            defaultTimezone: "Africa/Nairobi",      defaultCurrency: TransactionCurrency.USD },
  { code: "GH", name: "Ghana",            defaultTimezone: "Africa/Accra",        defaultCurrency: TransactionCurrency.USD },
  { code: "EG", name: "Egypt",            defaultTimezone: "Africa/Cairo",        defaultCurrency: TransactionCurrency.USD },
  { code: "IN", name: "India",            defaultTimezone: "Asia/Kolkata",        defaultCurrency: TransactionCurrency.USD },
  { code: "SG", name: "Singapore",        defaultTimezone: "Asia/Singapore",      defaultCurrency: TransactionCurrency.USD },
  { code: "MY", name: "Malaysia",         defaultTimezone: "Asia/Kuala_Lumpur",   defaultCurrency: TransactionCurrency.USD },
  { code: "JP", name: "Japan",            defaultTimezone: "Asia/Tokyo",          defaultCurrency: TransactionCurrency.USD },
  { code: "BR", name: "Brazil",           defaultTimezone: "America/Sao_Paulo",   defaultCurrency: TransactionCurrency.USD },
  { code: "MX", name: "Mexico",           defaultTimezone: "America/Mexico_City", defaultCurrency: TransactionCurrency.USD },
];

export const RESIDENCE_COUNTRIES: CountryInfo[] = raw.map((c) => ({ ...c, flag: flagFor(c.code) }));

export const findCountry = (code: string): CountryInfo | undefined =>
  RESIDENCE_COUNTRIES.find((c) => c.code === code);

/**
 * Curated IANA timezone list (extends each country default with major cities)
 * to give users a non-overwhelming select with sensible coverage.
 */
export const COMMON_TIMEZONES: string[] = Array.from(
  new Set([
    ...RESIDENCE_COUNTRIES.map((c) => c.defaultTimezone),
    "UTC",
    "Europe/Lisbon",
    "America/Los_Angeles",
    "America/Chicago",
    "America/Denver",
    "America/Vancouver",
    "Asia/Hong_Kong",
    "Asia/Shanghai",
    "Asia/Bangkok",
    "Africa/Abuja",
    "Africa/Casablanca",
  ]),
).sort();

export const detectBrowserTimezone = (): string => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
};

export const suggestTimezoneForCountry = (countryCode: string, browserTz?: string): string => {
  const country = findCountry(countryCode);
  if (!country) return browserTz ?? detectBrowserTimezone();
  // If the browser TZ is plausibly within the same continent as country default, prefer browser.
  if (browserTz && browserTz.split("/")[0] === country.defaultTimezone.split("/")[0]) {
    return browserTz;
  }
  return country.defaultTimezone;
};

export const SUPPORTED_CURRENCIES: TransactionCurrency[] = [
  TransactionCurrency.NGN,
  TransactionCurrency.USD,
  TransactionCurrency.GBP,
  TransactionCurrency.EUR,
];

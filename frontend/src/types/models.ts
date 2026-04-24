export enum TransactionCurrency {
  NGN = "NGN",
  USD = "USD",
  EUR = "EUR",
  GBP = "GBP",
}

export const FX_RATES: Record<TransactionCurrency, number> = {
  [TransactionCurrency.NGN]: 1,
  [TransactionCurrency.USD]: 0.00063,
  [TransactionCurrency.GBP]: 0.0005,
  [TransactionCurrency.EUR]: 0.00058,
};

export const CURRENCY_SYMBOLS: Record<TransactionCurrency, string> = {
  [TransactionCurrency.NGN]: "₦",
  [TransactionCurrency.USD]: "$",
  [TransactionCurrency.GBP]: "£",
  [TransactionCurrency.EUR]: "€",
};

export const CURRENCY_NAMES: Record<TransactionCurrency, string> = {
  [TransactionCurrency.NGN]: "Nigerian Naira",
  [TransactionCurrency.USD]: "US Dollar",
  [TransactionCurrency.GBP]: "British Pound",
  [TransactionCurrency.EUR]: "Euro",
};

export const getCurrencySymbol = (currency: TransactionCurrency) =>
  CURRENCY_SYMBOLS[currency];

export const getCurrencyName = (currency: TransactionCurrency) =>
  CURRENCY_NAMES[currency];

export const getFxRate = (currency: TransactionCurrency) =>
  FX_RATES[currency];

export enum PaymentMethod {
  FLUTTERWAVE = "flutterwave",
  PAYSTACK = "paystack",
  STRIPE = "stripe",
}

export enum PaymentState {
  IDLE = "idle",
  PROCESSING = "processing",
  SUCCESS = "success",
  FAILURE = "failure",
}

export enum Language {
  ENGLISH = "en-US",
  FRENCH = "FR",
}

export interface KeyValue{
  key: string;
  value: string;
}

export enum PropertyAssetPhotoCategory {
    All = "All",

    // HOUSES
    Kitchen = "Kitchen",
    Bathroom = "Bathroom",
    Bedroom = "Bedroom",
    Living = "Living",
    Dining = "Dining",
    OtherRooms = "Other rooms",
    Exterior = "Exterior",
    Amenities = "Amenities",

    // LAND
    FRONT_VIEW = "Front view"
}

export interface PropertyImage {
  title?: string;
  url: string;
  category?: PropertyAssetPhotoCategory;
}

export class Money {
  private value: number;
  private currency: TransactionCurrency;

  constructor(value: number = 0.0, currency: TransactionCurrency) {
    this.value = value;
    this.currency = currency;
  }

  static from(obj: { value: number; currency: TransactionCurrency }): Money {
    return new Money(obj.value, obj.currency);
  }

  getValue(): number {
    return this.value;
  }

  getCurrency(): TransactionCurrency {
    return this.currency;
  }

  plus(money: Money): Money {
    this.validateCurrency(money.getCurrency());
    this.validateNegativeCredit(money.getValue());
    return new Money(this.value + money.getValue(), this.currency);
  }

  minus(money: Money): Money {
    this.validateDebitBalance(money.getValue());
    this.validateCurrency(money.getCurrency());
    this.validateNegativeDebit(money.getValue());
    return new Money(this.value - money.getValue(), this.currency);
  }

  compare(other: Money): number {
    this.validateCurrency(other.getCurrency());

    if (isNaN(this.value) || isNaN(other.getValue())) return NaN;
    if (this.value < other.getValue()) return -1;
    if (this.value > other.getValue()) return 1;
    return 0;
  }

  isLessThan(other: Money): boolean {
    return this.compare(other) < 0;
  }

  isLessThanEquals(other: Money): boolean {
    return this.compare(other) <= 0;
  }

  isGreaterThan(other: Money): boolean {
    return this.compare(other) > 0;
  }

  isGreaterThanEquals(other: Money): boolean {
    return this.compare(other) >= 0;
  }

  isEqualTo(other: Money): boolean {
    return this.compare(other) === 0;
  }

  private validateCurrency(currency: TransactionCurrency): void {
    if (this.currency !== currency) {
      throw new Error("Money exception: currency mismatch");
    }
  }

  private validateNegativeCredit(amount: number): void {
    if (amount < 0) {
      throw new Error("Money exception: negative credit amount");
    }
  }

  private validateNegativeDebit(amount: number): void {
    if (amount < 0) {
      throw new Error("Money exception: negative debit amount");
    }
  }

  private validateDebitBalance(amount: number): void {
    if (this.value < 0 || this.value < amount) {
      throw new Error("Money exception: insufficient balance");
    }
  }
}

export enum PropertyType {
  LAND = "land",
  RESIDENTIAL = "residential",
  COMMERCIAL = "commercial",
  INDUSTRIAL = "industrial"
}

export interface Measurement {
  value: number;
  unit: MeasurementUnit;
}

export enum MeasurementUnit {
  METER = "meter",
  SQM = "sqm",
  FEET = "feet",
  SQF = "sqf",
  HECTARES = "hectares",
  ACRES = "acres",
  PLOTS = "plots"
}

export interface ExactLocation {
    address: string;
    country: string;
    state: string;
    lga?: string;
    city: string;
    groupingCity?: string;
    area: string;
    coordinates?: { lat: number; lng: number };
    street?: string;
    streetNumber?: string;
    postalCode?: string;
    placeId?: string;
  };

export interface BaseQueryDto {
  id?: string;                    // Unique ID
  dateUpdated?: string;         // ISO Date string (e.g. 2024-07-02T12:34:56Z)
  updatedBy?: string;           // Who updated the record
  deleted?: boolean;             // Whether deleted
  dateDeleted?: string;         // ISO Date string
  deletedBy?: string;           // Who deleted the record
  dateCreated?: string;         // ISO Date string
  createdBy?: string;           // Who created the record
  version?: number;              // The current version number of the record
}

export interface Page<T> {
  items: T[];               // List of items of type T
  page: number;            // Current page number
  pageSize: number;       // Number of items per page
  count: number;           // Number of items returned in this page
  total: number;           // Total number of items available
  totalPages: number;     // Total number of pages for the total data
  prevPage?: number;      // Previous page number, if any
  nextPage?: number;      // Next page number, if any
}

export interface PageRequest {
  page?: number;                  // Default: 0
  pageSize?: number;            // Default: 10
  // total_page?: number;           // Total record pages
  queryFields?: string;         // Comma-separated list of return fields
  exactStringValues?: boolean; // Default: true
  orderBy?: string;             // e.g. "username asc, firstname desc"
  where?: string;                // e.g. "dateCreated >="
  query?: string;                // e.g A four bedroom duplex in enugu state
}

export interface PageDetails {
  title: string;
  description: string;
  activeTab?: string;
}

export interface SuccessResponse<T> {
  status: string;          // always "success"
  code: string;            // typically "200"
  message?: string;
  traceId?: string;
  data?: T;
}

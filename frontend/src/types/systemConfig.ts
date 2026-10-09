// System config types (PRD §14/§18.5, §R.2) — mirror ConfigKey in app/domain/system_config/models.py.
export enum ConfigKey {
  DISPUTE_WINDOW_DAYS = "dispute_window_days",
  RECHECK_PRICE_PCT = "recheck_price_pct",
  AGENT_DISPUTE_DEFENCE_HOURS = "agent_dispute_defence_hours",
  COMMISSION_CLEARANCE_DAYS = "commission_clearance_days",
  COMMISSION_RESERVE_PCT = "commission_reserve_pct",
  CHARGEBACK_WINDOW_DAYS = "chargeback_window_days",
  COMMISSION_MIN_MARGIN_PCT = "commission_min_margin_pct",
  REMOTE_JOB_BONUS_NGN_KOBO = "remote_job_bonus_ngn_kobo",
  TASK_SLA_HOURS = "task_sla_hours",
  AGENT_LOW_PERFORMANCE_THRESHOLD = "agent_low_performance_threshold",
  AGENT_TOP_AGENT_ACCURACY_THRESHOLD = "agent_top_agent_accuracy_threshold",
  AGENT_WIDE_COVERAGE_STATES = "agent_wide_coverage_states",
  FIRST_TIME_DISCOUNT_PERCENT = "first_time_discount_percent",
  REFERRAL_CREDIT_NGN = "referral_credit_ngn",
  MAX_DISCOUNT_PERCENT = "max_discount_percent",
  CANCELLATION_SURCHARGE_PCT = "cancellation_surcharge_pct",
  PII_RETENTION_DAYS = "pii_retention_days",
  ERASURE_REQUEST_REVIEW_SLA_DAYS = "erasure_request_review_sla_days",
  SLA_AT_RISK_DAYS = "sla_at_risk_days",
  PAYOUT_SLA_BUSINESS_DAYS = "payout_sla_business_days",
  DISPUTE_MIN_DESCRIPTION_CHARS = "dispute_min_description_chars",
  SHARE_LINK_DEFAULT_EXPIRY_DAYS = "share_link_default_expiry_days",
  ANALYTICS_TREND_MONTHS = "analytics_trend_months",
  CHANNEL_ANALYTICS_WINDOW_DAYS = "channel_analytics_window_days",
  SUPPORT_HOURS_START = "support_hours_start",
  SUPPORT_HOURS_END = "support_hours_end",
  SUPPORT_SATURDAY_END = "support_saturday_end",
  OFFLINE_RESPONSE_HOURS = "offline_response_hours",
}

/** What a value counts — mirrors ConfigUnit in app/domain/system_config/models.py. No unit: a plain count. */
export enum ConfigUnit {
  MINOR_CURRENCY = "MINOR_CURRENCY", // stored in kobo; read and typed in naira
  MAJOR_CURRENCY = "MAJOR_CURRENCY", // stored and shown in whole naira
  PERCENT = "PERCENT",
}

export interface SystemConfigItem {
  key: ConfigKey;
  value: number | string | boolean | null;
  unit?: ConfigUnit | null;
  description?: string;
  dateUpdated?: string;
}

// System config types (PRD §14/§18.5) — mirror app/domain/system_config.
export enum ConfigKey {
  DISPUTE_WINDOW_DAYS = "dispute_window_days",
  RECHECK_PRICE_PCT = "recheck_price_pct",
  AGENT_DISPUTE_DEFENCE_HOURS = "agent_dispute_defence_hours",
}

export interface SystemConfigItem {
  key: ConfigKey;
  value: number | string | boolean | null;
  description?: string;
  dateUpdated?: string;
}

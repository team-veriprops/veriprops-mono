from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

import pandas as pd

from main.appodus_utils.db.types.money import TransactionCurrency, Money
from main.appodus_utils.integrations.messaging.models import MessageProviderName


@dataclass
class CostRecord:
    provider: str
    channel: str
    cost: Money
    message_id: str
    timestamp: datetime
    extras: Optional[Dict] = None


class CostTracker:
    def __init__(self):
        self.records = []
        # self.rates = {
        #     "twilio_sms": {"us": 0.0075, "international": 0.05},
        #     "termii_sms": {"ng": 2.5, "international": 3.5},  # in NGN
        #     "sendgrid_email": 0.0001,  # per email
        #     "whatsapp_business": {
        #         "template": 0.01,
        #         "session": 0.005,
        #         "media": 0.015
        #     },
        #     "firebase_push": 0.0001  # per push
        # }

    # def calculate_cost(self, provider: str, channel: str, details: Dict) -> float:
    #     """Calculate cost based on provider and message details"""
    #     rate = self.rates.get(provider)
    #
    #     if not rate:
    #         return 0.0
    #
    #     if provider == MessageProviderName.TWILIO_SMS:
    #         country = details.get("country", "international")
    #         return rate.get(country, rate["international"])
    #
    #     elif provider == MessageProviderName.TERMII_SMS:
    #         country = details.get("country", "international")
    #         return rate.get(country, rate["international"]) / 100  # Convert to USD
    #
    #     elif provider == MessageProviderName.WHATSAPP_BUSINESS:
    #         message_type = details.get("message_type", "template")
    #         return rate.get(message_type, 0.01)
    #
    #     return rate if isinstance(rate, float) else 0.0

    def record_cost(self, record: CostRecord):
        self.records.append(record)

    def get_cost_summary(self, period: str = "daily") -> pd.DataFrame:
        """Generate cost reports"""
        df = pd.DataFrame([r.__dict__ for r in self.records])
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        if period == "daily":
            return df.groupby([
                pd.Grouper(key='timestamp', freq='D'),
                'provider',
                'channel'
            ])['cost'].sum().unstack()

        elif period == "monthly":
            return df.groupby([
                pd.Grouper(key='timestamp', freq='M'),
                'provider',
                'channel'
            ])['cost'].sum().unstack()

        return df


# Initialize cost tracker
cost_tracker = CostTracker()

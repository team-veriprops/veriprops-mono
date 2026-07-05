"""Fraud scanner (§4.7): the send-time flag rules and the clean fast lane."""
import pytest

from main.app.domain.communication.fraud_scan import FraudCategory, is_clean, scan_message


@pytest.mark.parametrize(
    "body",
    [
        "Thanks, I'll be at the site on Tuesday morning.",
        "The registry search is complete and the title looks clear.",
        "Please confirm the plot boundary on the north side.",
        "",
    ],
)
def test_clean_messages_take_the_fast_lane(body):
    assert scan_message(body) == []
    assert is_clean(body) is True


@pytest.mark.parametrize(
    "body,category",
    [
        ("Call me on 08031234567", FraudCategory.PHONE),
        ("My number is +234 803 123 4567", FraudCategory.PHONE),
        ("email me at agent@example.com", FraudCategory.EMAIL),
        ("see https://wa.me/2348012345678", FraudCategory.URL),
        ("check example.com for details", FraudCategory.URL),
        ("send to account number 0123456789", FraudCategory.BANKING),
        ("my bvn is available", FraudCategory.BANKING),
        ("dm me on instagram", FraudCategory.SOCIAL),
        ("reach me @john_doe", FraudCategory.SOCIAL),
        ("let's talk outside the platform", FraudCategory.OFF_PLATFORM),
        ("contact me directly instead", FraudCategory.OFF_PLATFORM),
    ],
)
def test_flagged_messages_are_categorised(body, category):
    result = scan_message(body)
    assert category in result
    assert is_clean(body) is False


def test_multiple_categories_flagged_in_stable_order():
    body = "email me agent@example.com or call 08031234567"
    result = scan_message(body)
    # Declaration order: EMAIL before PHONE.
    assert result == [FraudCategory.EMAIL, FraudCategory.PHONE]

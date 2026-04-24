from pydantic import field_validator

from main.appodus_utils import Object


class PhoneNumber(Object):
    dial_code: str
    number: str

    @property
    def internation_number(self)-> str:
        return f"{self.dial_code}{self.number}"

    @field_validator('number', mode='before')
    def normalize_number(cls, v: str) -> str:
        if not v:
            raise ValueError("Phone number cannot be empty")
        # Remove non-digit characters
        digits_only = ''.join(filter(lambda c: c.isdigit(), v))
        # Remove leading zeros
        normalized = digits_only.lstrip('0')
        if not normalized:
            raise ValueError("Phone number cannot be all zeros")
        return normalized

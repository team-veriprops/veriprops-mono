from pydantic import field_validator

from main.appodus_utils import Object


class PhoneNumber(Object):
    dial_code: str
    number: str

    @classmethod
    def from_e164(cls, value: str) -> "PhoneNumber":
        """Build a recipient from a stored E.164 number (``+2348012345678``).

        The country/subscriber split is deliberately **not** reconstructed — doing that
        correctly needs a dial-code table this type does not carry, and guessing one would
        put a wrong country code into a field callers could believe. Every consumer reads
        ``international_number``, which round-trips exactly, so the whole number lives in
        ``number`` and ``dial_code`` carries only the leading ``+``.
        """
        digits = "".join(c for c in (value or "") if c.isdigit())
        if not digits:
            raise ValueError("Phone number cannot be empty")
        return cls(dial_code="+", number=digits)

    @property
    def international_number(self)-> str:
        digits = "".join(c for c in (self.dial_code + self.number) if c.isdigit())
        return f"+{digits}"

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

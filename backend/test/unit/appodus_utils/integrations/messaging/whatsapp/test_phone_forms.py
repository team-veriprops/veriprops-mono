"""Phone-number forms on the WhatsApp seam (PRD §7.3.1).

Meta identifies a participant by digits-only `wa_id`; the rest of the app keys identity
on E.164. The two are one character apart, so the conversion is pinned rather than
re-derived at each call site.
"""
from main.appodus_utils.integrations.messaging.providers.whatsapp.phone import (
    to_e164,
    to_wa_recipient,
)


class TestPhoneForms:
    def test_wa_id_becomes_the_identity_form(self):
        assert to_e164("2348012345678") == "+2348012345678"

    def test_identity_form_becomes_a_wa_recipient(self):
        assert to_wa_recipient("+2348012345678") == "2348012345678"

    def test_both_directions_tolerate_human_formatting(self):
        assert to_e164("+234 801 234 5678") == "+2348012345678"
        assert to_wa_recipient("+234-801-234-5678") == "2348012345678"

    def test_round_trips(self):
        assert to_wa_recipient(to_e164("2348012345678")) == "2348012345678"

    def test_empty_input_yields_empty_output_rather_than_a_bare_plus(self):
        # A lone "+" would pass a naive truthiness check and fail deep in a provider.
        assert to_e164("") == ""
        assert to_e164("no digits here") == ""
        assert to_wa_recipient("") == ""

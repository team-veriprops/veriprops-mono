"""Widget attribution markers (§26.4.1, §26.10, D85).

The page code arrives as literal text the customer's phone typed for them. Two things have
to be true at once: §26.10 gets its demand signal, and nothing that reads the message *as
words* — the classifier, the guardrails, the agent console — ever sees the markup.
"""
from main.appodus_utils.integrations.messaging.providers.whatsapp.attribution import (
    extract_page_code,
)


class TestExtraction:
    def test_the_widgets_own_prefill_is_read_and_cleaned(self):
        code, cleaned = extract_page_code("Hi Veriprops! [ref: web-home]")

        assert code == "web-home"
        assert cleaned == "Hi Veriprops!"

    def test_the_continue_button_marker_leaves_the_reference_behind(self):
        # §26.4.3/D58 — the VID is what the bot matches on, so stripping the marker must
        # not take the customer's case reference with it.
        code, cleaned = extract_page_code("Continue VP-2026-0001 [ref: web-portal]")

        assert code == "web-portal"
        assert cleaned == "Continue VP-2026-0001"

    def test_an_unlisted_page_code_is_accepted_as_written(self):
        # The frontend derives `web-<segment>` for any new page without a table edit, so
        # an unfamiliar code is a new page — rejecting it would lose real attribution.
        code, _cleaned = extract_page_code("Hello [ref: web-some-new-landing]")

        assert code == "web-some-new-landing"

    def test_the_code_is_normalized_to_lower_case(self):
        code, _cleaned = extract_page_code("Hi [ref: WEB-Pricing]")

        assert code == "web-pricing"

    def test_spacing_variations_still_match(self):
        for raw in ("[ref:web-home]", "[ref : web-home]", "[ Ref: web-home ]"):
            code, _cleaned = extract_page_code(f"Hi {raw}")
            assert code == "web-home", raw


class TestWhatIsLeftBehind:
    def test_a_message_that_is_only_a_marker_has_no_words_left(self):
        # None, not "". A message with no words is a greeting the §26.6.1 welcome answers;
        # an empty string would look like a message that trailed off.
        code, cleaned = extract_page_code("[ref: web-home]")

        assert code == "web-home"
        assert cleaned is None

    def test_an_ordinary_message_passes_through_untouched(self):
        code, cleaned = extract_page_code("how much does a verification cost?")

        assert code is None
        assert cleaned == "how much does a verification cost?"

    def test_nothing_in_nothing_out(self):
        assert extract_page_code(None) == (None, None)
        assert extract_page_code("") == (None, "")

    def test_a_forwarded_second_marker_does_not_overwrite_the_first(self):
        # A forwarded conversation can carry someone else's marker. The page *this*
        # customer arrived from is the one their own phone put there first.
        code, cleaned = extract_page_code("Hi [ref: web-home] fwd [ref: web-pricing]")

        assert code == "web-home"
        assert "ref:" not in cleaned

    def test_a_marker_shaped_thing_the_customer_typed_is_not_a_code(self):
        # Guardrails and the classifier read `cleaned`, so over-eager stripping would
        # silently delete words a customer meant.
        code, cleaned = extract_page_code("is [reference: 12] the plot number?")

        assert code is None
        assert cleaned == "is [reference: 12] the plot number?"

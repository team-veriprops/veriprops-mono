"""§7.6.3 non-text inbound policy (WA-06, WA-38).

Three rows in the PRD table, three different answers, and getting them confused is not a
cosmetic failure. Before this flow existed a customer who photographed their survey plan
got "Sorry, I didn't quite get that" — the image kinds were left out of the bot's
unreadable set on the assumption the upload handoff would catch them, and the handoff had
not been built.

The rule underneath all of it is the **evidence rule** (§7.1.6): what arrives over WhatsApp
is never what the verifiers work from. So a document is not refused — it is redirected to
the upload page, where it counts.
"""
from datetime import date

from main.app.domain.channel.whatsapp.bot.flows import media as media_flow
from main.app.domain.channel.whatsapp.bot.flows import status as status_flow
from main.app.domain.channel.whatsapp.bot.projection import ChannelState
from main.app.domain.channel.whatsapp.bot.session.models import EscalationReason
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import InboundKind


def _case(vid="VP-2026-0001", label="12 Admiralty Way, Lekki"):
    return status_flow.CaseSummary(
        vid=vid,
        property_label=label,
        status_label="Under review",
        channel_state=ChannelState.VERIFYING,
        sla_due_date=date(2026, 9, 20),
    )


class TestWhichTurnsThisFlowOwns:
    def test_every_media_kind_is_claimed(self):
        for kind in (
            InboundKind.IMAGE, InboundKind.DOCUMENT, InboundKind.VIDEO,
            InboundKind.AUDIO, InboundKind.STICKER, InboundKind.LOCATION,
            InboundKind.CONTACTS, InboundKind.UNSUPPORTED,
        ):
            assert media_flow.is_media(kind) is True, kind

    def test_plain_text_is_not_media(self):
        assert media_flow.is_media(InboundKind.TEXT) is False

    def test_a_menu_tap_is_not_media(self):
        # An INTERACTIVE payload is a button/list selection. Routing it here would answer
        # a customer's tap on the bot's own menu with an apology.
        assert media_flow.is_media(InboundKind.INTERACTIVE) is False


class TestDocuments:
    def test_one_open_case_gets_an_upload_link_for_that_case(self):
        outcome = media_flow.render(
            InboundKind.IMAGE, is_linked=True, cases=[_case()]
        )

        assert outcome.upload_for_vid == "VP-2026-0001"
        assert outcome.is_escalation is False

    def test_a_forwarded_pdf_is_treated_the_same_as_a_photo(self):
        # Photographing the C-of-O and forwarding the lawyer's scan are the same intent.
        outcome = media_flow.render(
            InboundKind.DOCUMENT, is_linked=True, cases=[_case()]
        )

        assert outcome.upload_for_vid == "VP-2026-0001"

    def test_several_cases_are_asked_about_rather_than_guessed(self):
        cases = [_case("VP-2026-0001"), _case("VP-2026-0002", "9 Bourdillon, Ikoyi")]

        outcome = media_flow.render(InboundKind.IMAGE, is_linked=True, cases=cases)

        assert outcome.awaits_choice is True
        assert outcome.offered_vids == ("VP-2026-0001", "VP-2026-0002")
        # No link yet: an `upload` token authorizes writing to exactly one case.
        assert outcome.upload_for_vid is None

    def test_the_choice_prompt_lists_both_cases(self):
        cases = [_case("VP-2026-0001"), _case("VP-2026-0002", "9 Bourdillon, Ikoyi")]

        outcome = media_flow.render(InboundKind.IMAGE, is_linked=True, cases=cases)

        assert "VP-2026-0001" in outcome.text
        assert "9 Bourdillon, Ikoyi" in outcome.text


class TestOnlyAPaidCaseCanReceiveADocument:
    """A document needs a case file to go into, and an unpaid case does not have one.

    The live drive-through caught this: the bot offered an upload link for a DRAFT, and the
    landing 500'd because a draft has no tier — it has not been quoted, let alone paid for.
    The cut is at payment rather than anywhere later: a customer sending a document about a
    *delivered* case is disputing or re-checking it, which is exactly what §7.6.3 is for.
    Filtering here also means the landing's required fields hold by construction, rather
    than through a defensive default that would have hidden the same mistake.
    """

    def _case_in(self, state, vid="VP-2026-0009"):
        return status_flow.CaseSummary(
            vid=vid,
            property_label="12 Admiralty Way, Lekki",
            status_label="Draft",
            channel_state=state,
        )

    def test_a_draft_is_not_offered_as_an_upload_target(self):
        outcome = media_flow.render(
            InboundKind.IMAGE, is_linked=True,
            cases=[self._case_in(ChannelState.INTAKE_IN_PROGRESS)],
        )

        assert outcome.upload_for_vid is None
        assert outcome.awaits_choice is False

    def test_an_unpaid_case_is_not_offered_either(self):
        outcome = media_flow.render(
            InboundKind.IMAGE, is_linked=True,
            cases=[self._case_in(ChannelState.PAYMENT_PENDING)],
        )

        assert outcome.upload_for_vid is None

    def test_a_delivered_case_still_accepts_a_document(self):
        # A document arriving after the report is a dispute or a re-check, not a mistake.
        outcome = media_flow.render(
            InboundKind.IMAGE, is_linked=True,
            cases=[self._case_in(ChannelState.DELIVERED)],
        )

        assert outcome.upload_for_vid == "VP-2026-0009"

    def test_every_state_from_payment_onward_is_open_to_uploads(self):
        for state in (
            ChannelState.PAID, ChannelState.VERIFYING, ChannelState.FIELD_INSPECTION,
            ChannelState.REPORT_READY, ChannelState.DELIVERED, ChannelState.CLOSED,
        ):
            outcome = media_flow.render(
                InboundKind.IMAGE, is_linked=True, cases=[self._case_in(state)]
            )

            assert outcome.upload_for_vid == "VP-2026-0009", state

    def test_a_draft_alongside_a_live_case_does_not_force_a_question(self):
        # Only one case can actually take the document, so asking would be noise.
        outcome = media_flow.render(
            InboundKind.IMAGE, is_linked=True,
            cases=[
                self._case_in(ChannelState.INTAKE_IN_PROGRESS, "VP-2026-0001"),
                self._case_in(ChannelState.VERIFYING, "VP-2026-0002"),
            ],
        )

        assert outcome.upload_for_vid == "VP-2026-0002"
        assert outcome.awaits_choice is False

    def test_a_draft_is_never_listed_in_the_choice_prompt(self):
        outcome = media_flow.render(
            InboundKind.IMAGE, is_linked=True,
            cases=[
                self._case_in(ChannelState.INTAKE_IN_PROGRESS, "VP-2026-0001"),
                self._case_in(ChannelState.VERIFYING, "VP-2026-0002"),
                self._case_in(ChannelState.PAID, "VP-2026-0003"),
            ],
        )

        assert outcome.offered_vids == ("VP-2026-0002", "VP-2026-0003")
        assert "VP-2026-0001" not in outcome.text


class TestTheEvidenceRuleIsAlwaysStated:
    def test_when_a_link_is_offered_the_caller_still_states_it(self):
        from main.app.domain.channel.whatsapp.bot import content

        reply = content.document_received_with_link("https://veriprops.ng/wa/upload/tok")

        assert "don't go into your verification file" in reply
        assert "https://veriprops.ng/wa/upload/tok" in reply

    def test_an_unlinked_number_is_told_the_rule_and_offered_linking(self):
        outcome = media_flow.render(InboundKind.IMAGE, is_linked=False, cases=[])

        assert "verification file" in outcome.text
        assert "link my account" in outcome.text

    def test_an_unlinked_number_is_never_handed_an_upload_link(self):
        # §7.4.3 — an `upload` token names a customer and a case. Issuing one off a phone
        # number alone would mean guessing whose file the document belongs in.
        outcome = media_flow.render(InboundKind.IMAGE, is_linked=False, cases=[])

        assert outcome.upload_for_vid is None
        assert outcome.awaits_choice is False

    def test_a_linked_customer_with_nothing_open_is_invited_to_start_one(self):
        outcome = media_flow.render(InboundKind.IMAGE, is_linked=True, cases=[])

        assert "verification file" in outcome.text
        assert "start a verification" in outcome.text
        assert outcome.upload_for_vid is None


class TestVoiceNotes:
    def test_a_voice_note_gets_its_own_reason_not_the_generic_one(self):
        # §7.10 asks for voice-note volume by name, so it cannot be pooled with pins and
        # contact cards under one counter.
        outcome = media_flow.render(InboundKind.AUDIO, is_linked=True, cases=[_case()])

        assert outcome.escalation_reason == EscalationReason.VOICE_NOTE

    def test_the_copy_promises_a_person_will_listen(self):
        from main.app.domain.channel.whatsapp.bot import content
        from main.app.domain.channel.whatsapp.bot.support_hours import Coverage, CoverageState

        reply = content.escalation(
            EscalationReason.VOICE_NOTE,
            Coverage(state=CoverageState.OPEN, response_hours=12),
        )

        assert "listen" in reply

    def test_a_voice_note_is_never_answered_with_an_upload_link(self):
        # The evidence rule bites hardest here: a recording is not a document, and the
        # upload page has nothing to do with it.
        outcome = media_flow.render(InboundKind.AUDIO, is_linked=True, cases=[_case()])

        assert outcome.upload_for_vid is None


class TestEverythingElseGoesToAPerson:
    def test_a_location_pin_is_acknowledged_and_routed(self):
        outcome = media_flow.render(InboundKind.LOCATION, is_linked=True, cases=[_case()])

        assert outcome.escalation_reason == EscalationReason.UNSUPPORTED_MEDIA

    def test_a_contact_card_is_acknowledged_and_routed(self):
        outcome = media_flow.render(InboundKind.CONTACTS, is_linked=True, cases=[_case()])

        assert outcome.escalation_reason == EscalationReason.UNSUPPORTED_MEDIA

    def test_a_video_is_routed_rather_than_offered_the_upload_page(self):
        outcome = media_flow.render(InboundKind.VIDEO, is_linked=True, cases=[_case()])

        assert outcome.escalation_reason == EscalationReason.UNSUPPORTED_MEDIA

    def test_a_type_meta_added_after_this_code_was_written_is_still_answered(self):
        # Never dropped — that is the whole promise of §7.6.3's last row.
        outcome = media_flow.render(
            InboundKind.UNSUPPORTED, is_linked=True, cases=[_case()]
        )

        assert outcome.is_escalation is True


class TestResolvingTheChoice:
    def test_the_position_selects_a_case(self):
        cases = [_case("VP-2026-0001"), _case("VP-2026-0002")]

        assert media_flow.resolve_choice(cases, "2").vid == "VP-2026-0002"

    def test_the_reference_selects_a_case(self):
        cases = [_case("VP-2026-0001"), _case("VP-2026-0002")]

        assert media_flow.resolve_choice(cases, "vp-2026-0001").vid == "VP-2026-0001"

    def test_something_else_entirely_is_not_a_choice(self):
        # The engine reads None as "they moved on" and classifies the message fresh,
        # rather than trapping a customer who changed their mind.
        cases = [_case("VP-2026-0001"), _case("VP-2026-0002")]

        assert media_flow.resolve_choice(cases, "actually what does it cost?") is None

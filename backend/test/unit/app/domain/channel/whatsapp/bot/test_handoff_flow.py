"""§7.3.4's pay and report handoffs (WA-17, §7.4.2).

§7.3.4 marks three WhatsApp actions HANDOFF: upload, pay, and view report. Only the first
had a producer — a document arriving is something that *happens to* the bot, so §7.6.3
built it. The other two are things a customer **asks** for, and there was no intent for
either: "how do I pay?" and "send me my report" both fell through to "I didn't quite get
that", leaving the `/wa/pay/<token>` and `/wa/report/<token>` landings — built, tested, and
deployed — unreachable from a real conversation.

The rule this flow exists to hold: **eligibility is read off the §7.3.2 projection, never
off a raw status.** A case is payable at `PAYMENT_PENDING` and readable at `DELIVERED`, and
both are stage names `projection.py` already owns. Re-deriving them from
`VerificationStatus` here would put the same mapping in a second place, and the two would
drift the first time a status was added.

The sharpest case below is `REPORT_READY`, whose name is a trap: it projects from
`UNDER_REVIEW`, where the report exists but has not passed the §8 release gate. Reading
"a report exists" as "the customer may have it" is exactly the mistake the gate prevents.
"""
from datetime import date

import pytest

from main.app.domain.channel.whatsapp.bot import content
from main.app.domain.channel.whatsapp.bot.capabilities import ChannelAction
from main.app.domain.channel.whatsapp.bot.flows import handoff as handoff_flow
from main.app.domain.channel.whatsapp.bot.flows import status as status_flow
from main.app.domain.channel.whatsapp.bot.projection import ChannelState


def _case(vid="VP-2026-0001", label="12 Admiralty Way, Lekki", state=ChannelState.PAYMENT_PENDING):
    return status_flow.CaseSummary(
        vid=vid,
        property_label=label,
        status_label="Awaiting payment",
        channel_state=state,
        sla_due_date=date(2026, 9, 20),
    )


class TestEligibilityComesFromTheProjection:
    def test_only_payment_pending_is_payable(self):
        # Every other stage either has nothing to pay for yet or has already been paid.
        for state in ChannelState:
            eligible = handoff_flow.eligible_cases(
                ChannelAction.PAY, [_case(state=state)]
            )
            assert bool(eligible) is (state is ChannelState.PAYMENT_PENDING), state

    def test_only_a_delivered_case_is_readable(self):
        for state in ChannelState:
            eligible = handoff_flow.eligible_cases(
                ChannelAction.VIEW_REPORT, [_case(state=state)]
            )
            assert bool(eligible) is (state is ChannelState.DELIVERED), state

    def test_a_report_awaiting_release_is_not_offered(self):
        # The trap in the name: `REPORT_READY` projects from `UNDER_REVIEW` — the report
        # exists but has not passed the §8 release gate. A link here would hand the
        # customer the very draft the gate exists to hold back.
        eligible = handoff_flow.eligible_cases(
            ChannelAction.VIEW_REPORT, [_case(state=ChannelState.REPORT_READY)]
        )

        assert eligible == []

    def test_a_delivered_case_still_has_a_report_to_re_read(self):
        # §7.4.2's recovery path: the report link is minted on request, and a customer
        # coming back a month later is the ordinary case, not an edge one.
        eligible = handoff_flow.eligible_cases(
            ChannelAction.VIEW_REPORT, [_case(state=ChannelState.DELIVERED)]
        )

        assert [case.vid for case in eligible] == ["VP-2026-0001"]

    def test_asking_about_a_non_handoff_action_is_a_caller_bug(self):
        # LEARN is FULL on WhatsApp — it has nothing to hand off — so answering with an
        # empty list would quietly hide the mistake.
        with pytest.raises(ValueError):
            handoff_flow.eligible_cases(ChannelAction.LEARN, [_case()])


class TestPay:
    def test_one_payable_case_gets_a_link_for_that_case(self):
        outcome = handoff_flow.render(ChannelAction.PAY, is_linked=True, cases=[_case()])

        assert outcome.link_for_vid == "VP-2026-0001"
        assert outcome.awaits_choice is False

    def test_several_payable_cases_are_asked_about_rather_than_guessed(self):
        cases = [_case("VP-2026-0001"), _case("VP-2026-0002", "9 Bourdillon, Ikoyi")]

        outcome = handoff_flow.render(ChannelAction.PAY, is_linked=True, cases=cases)

        assert outcome.link_for_vid is None
        assert outcome.offered_vids == ("VP-2026-0001", "VP-2026-0002")
        # The same numbered list the status and document flows use, so a customer never
        # has to learn a second way of answering "which one?".
        assert "1. 12 Admiralty Way, Lekki (VP-2026-0001)" in outcome.text

    def test_a_paid_case_is_not_offered_for_payment(self):
        outcome = handoff_flow.render(
            ChannelAction.PAY, is_linked=True, cases=[_case(state=ChannelState.VERIFYING)]
        )

        assert outcome.link_for_vid is None
        assert outcome.awaits_choice is False
        assert outcome.text == content.pay_no_case()

    def test_an_unlinked_number_is_never_handed_a_payment_link(self):
        # A pay token names a customer and a case. Issuing one off a phone number alone
        # would be guessing whose money is being asked for.
        outcome = handoff_flow.render(ChannelAction.PAY, is_linked=False, cases=[])

        assert outcome.link_for_vid is None
        assert outcome.text == content.handoff_unlinked(ChannelAction.PAY)


class TestReport:
    def test_one_delivered_case_gets_a_report_link(self):
        outcome = handoff_flow.render(
            ChannelAction.VIEW_REPORT,
            is_linked=True,
            cases=[_case(state=ChannelState.DELIVERED)],
        )

        assert outcome.link_for_vid == "VP-2026-0001"

    def test_a_case_still_in_the_field_has_no_report_yet(self):
        outcome = handoff_flow.render(
            ChannelAction.VIEW_REPORT,
            is_linked=True,
            cases=[_case(state=ChannelState.FIELD_INSPECTION)],
        )

        assert outcome.link_for_vid is None
        assert outcome.text == content.report_no_case()

    def test_an_unlinked_number_is_never_handed_a_report_link(self):
        outcome = handoff_flow.render(ChannelAction.VIEW_REPORT, is_linked=False, cases=[])

        assert outcome.link_for_vid is None
        assert outcome.text == content.handoff_unlinked(ChannelAction.VIEW_REPORT)

    def test_the_two_actions_do_not_answer_each_other(self):
        # A customer with a payable case asking for their report must not be handed a
        # payment link, and vice versa — the link authorizes a different action.
        payable_only = [_case(state=ChannelState.PAYMENT_PENDING)]

        assert handoff_flow.render(
            ChannelAction.VIEW_REPORT, is_linked=True, cases=payable_only
        ).link_for_vid is None


class TestChoosing:
    def test_a_position_selects_the_case_at_that_position(self):
        cases = [_case("VP-2026-0001"), _case("VP-2026-0002", "9 Bourdillon, Ikoyi")]

        assert handoff_flow.resolve_choice(cases, "2").vid == "VP-2026-0002"

    def test_a_reference_selects_by_name(self):
        cases = [_case("VP-2026-0001"), _case("VP-2026-0002", "9 Bourdillon, Ikoyi")]

        assert handoff_flow.resolve_choice(cases, "vp-2026-0001").vid == "VP-2026-0001"

    def test_changing_the_subject_is_not_a_choice(self):
        # None means "they moved on", which the engine answers by classifying fresh
        # rather than nagging — the same contract as the status and document flows.
        assert handoff_flow.resolve_choice([_case()], "actually what does it cost?") is None


class TestCopy:
    def test_the_payment_link_carries_the_pledge(self):
        # §7.1.1 — the pledge rides *every* payment handoff. This is the message that
        # sends someone to a payment page, so it is the one that matters most.
        assert content.PAYMENT_PLEDGE in content.pay_with_link("https://example.test/wa/pay/t")

    def test_the_report_message_does_not_claim_to_be_a_payment(self):
        body = content.report_with_link("https://example.test/wa/report/t")

        assert "https://example.test/wa/report/t" in body
        assert content.PAYMENT_PLEDGE not in body

    def test_the_unlinked_answer_names_the_linking_route(self):
        for action in (ChannelAction.PAY, ChannelAction.VIEW_REPORT):
            assert "link my account" in content.handoff_unlinked(action)

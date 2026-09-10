"""Handoff redemption (PRD §26.4.2, §26.5, D50/D51).

Turns a signed token into a short-lived, single-action grant.

**Redeem once, then hold a grant.** Taken literally, "record the jti on redemption" would
burn a link on the first page load — including a refresh, a back-navigation, or a link
preview fetched by WhatsApp itself. So redemption happens exactly once and issues a grant
scoped to that one intent and case, valid only until the token's own expiry (D51). The
customer can reload the page; a forwarded copy of the token is already dead.

**A grant is not a session.** It authorizes one action on one case and carries no account
access — completing a payment does not log anyone in (§26.5). The three intents are also
deliberately unequal (D50): `pay` is the only one that acts on the token alone, because
the worst case for a leaked pay link is a stranger paying someone else's bill. `upload`
and `report` hand off to the authenticated portal instead: portal uploads are canonical
evidence (§26.1.6) and Decision B specifies an authenticated portal link for reports, so
neither may rest on a link that can be forwarded.
"""
from __future__ import annotations

from typing import Optional

from kink import inject

from main.app.domain.channel.whatsapp.handoff.models import (
    CreateHandoffTokenRedemptionDto,
    HandoffIntent,
    HandoffTokenRedemption,
)
from main.app.domain.channel.whatsapp.handoff.repo import HandoffTokenRedemptionRepo
from main.app.domain.channel.whatsapp.handoff.tokens import (
    issue_intake_token,
    HandoffClaims,
    HandoffTokenError,
    decode_handoff_token,
    issue_handoff_token,
    issue_link_token,
)
from main.app.domain.verification.service import VerificationService
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class HandoffTokenService:
    def __init__(
        self,
        handoff_token_redemption_repo: HandoffTokenRedemptionRepo,
        verification_service: VerificationService,
    ):
        self._handoff_token_redemption_repo = handoff_token_redemption_repo
        self._verifications = verification_service

    async def issue(self, customer_id: str, case_id: str, intent: HandoffIntent) -> str:
        """Mint a handoff link for a case the customer owns.

        Ownership is checked at issue time so a bug in a bot flow cannot mint a token
        pointing at someone else's case — the token itself is then trusted downstream
        precisely because it could only have been created here.
        """
        await self._verifications.get_owned(case_id, customer_id)
        return issue_handoff_token(customer_id=customer_id, case_id=case_id, intent=intent)

    async def issue_link(self, phone_e164: str) -> str:
        """Mint a §26.4.4 linking link for a WhatsApp number.

        There is deliberately no ownership check: the whole point is that this number has
        no account yet. The token proves only *which* number crossed to the website —
        identity is still established by the OTP that follows.
        """
        return issue_link_token(phone_e164)

    async def issue_intake(self, phone_e164: str) -> str:
        """Mint a §5.1 intake link for a WhatsApp number (D69/D71).

        No ownership check, for the same reason `issue_link` has none: this number has no
        account yet — establishing one is what the landing is for. The token names the
        number so the landing can find the answers the bot collected; it carries none of
        them.
        """
        return issue_intake_token(phone_e164)

    async def redeem(
        self,
        token: str,
        intent: HandoffIntent,
        redeemed_ip: Optional[str] = None,
        holder_jti: Optional[str] = None,
    ) -> HandoffClaims:
        """Verify a token, spend its nonce, and return the claims it authorizes.

        ``holder_jti`` is the nonce named by the caller's existing grant, if it has one.
        A caller presenting the token it *already* redeemed is refreshing or navigating
        back, not replaying — single-use must not mean single-pageview (D51) — so it gets
        its context again. Anyone else presenting the same token is holding a forwarded
        copy, and gets nothing.

        Raises ``HandoffTokenError`` for every failure mode — expired, replayed,
        tampered, wrong intent — with one indistinguishable message, so probing a link
        reveals nothing about why it did not work.
        """
        claims = decode_handoff_token(token)
        # The landing route says which action it is serving; a `report` token opened at
        # the payment landing is not a payment authorization.
        if claims.intent != intent:
            raise HandoffTokenError()

        if await self._handoff_token_redemption_repo.get_by_jti(claims.jti) is not None:
            if holder_jti == claims.jti:
                return claims
            raise HandoffTokenError()

        await self._handoff_token_redemption_repo.create_return_model(
            CreateHandoffTokenRedemptionDto(
                jti=claims.jti,
                intent=claims.intent,
                case_id=claims.case,
                customer_id=claims.sub,
                phone_e164=claims.phone,
                redeemed_at=Utils.datetime_now(),
                redeemed_ip=redeemed_ip,
            )
        )
        return claims

    async def decode_link(self, token: str) -> HandoffClaims:
        """Read a `link` token without spending it.

        Starting a linking attempt must not burn the bot's link: a code can fail to
        arrive, and a customer who asks for a resend should not find the page dead. The
        nonce is spent on confirmation instead, which is the step that actually changes
        anything.
        """
        claims = decode_handoff_token(token)
        if claims.intent != HandoffIntent.LINK:
            raise HandoffTokenError()
        if await self._handoff_token_redemption_repo.get_by_jti(claims.jti) is not None:
            raise HandoffTokenError()
        return claims

    async def redeem_link(self, token: str, redeemed_ip: Optional[str] = None) -> HandoffClaims:
        """Spend a `link` token — one completed linking attempt per link the bot sent."""
        return await self.redeem(token, HandoffIntent.LINK, redeemed_ip=redeemed_ip)

    async def redeem_intake(self, token: str, redeemed_ip: Optional[str] = None) -> HandoffClaims:
        """Spend an `intake` token — one seeded draft per link the bot sent.

        Spent on redemption rather than on submit: unlike linking (where a failed OTP must
        not strand the customer), redemption itself is the whole action here, and the D51
        grant is what lets the holder reload the page afterwards.
        """
        return await self.redeem(token, HandoffIntent.INTAKE, redeemed_ip=redeemed_ip)

    async def redemption_for(self, jti: str) -> Optional[HandoffTokenRedemption]:
        """The redemption record for a nonce, if it has been spent."""
        return await self._handoff_token_redemption_repo.get_by_jti(jti)

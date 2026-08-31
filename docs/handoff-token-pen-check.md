# Handoff token pen-check list (PRD §7.11)

The §7.11 launch gate reads "Token service pen-checked (replay, expiry, scope
containment)". This is the checklist that gate refers to.

The threat model is the PRD's own (§7.5): handoff links travel through WhatsApp, where
forwarding a message is ordinary behaviour, so **a leaked or forwarded link must expose at
most one expired, single-use, single-action grant — never an account.** Every item below
is an attempt to break that sentence.

Items marked ✅ are covered by automated tests today; the file column says where. The
remaining items need a human with a proxy against a running stack, and are the actual
gate.

## Covered by automated tests

| # | Attack | Expected | Covered by |
|---|--------|----------|------------|
| 1 | Present a link a second time from another browser | Refused, recovery page | `test_handoff_service.py::test_the_same_link_cannot_be_redeemed_twice`, `wa-handoff.spec.ts` UAT-WAH-02 |
| 2 | Present an expired link | Refused | `test_handoff_token.py::test_rejects_an_expired_token` |
| 3 | Edit the payload (swap the case id) | Refused | `test_handoff_token.py::test_rejects_a_tampered_payload` |
| 4 | Re-sign with a different key | Refused | `test_handoff_token.py::test_rejects_a_token_signed_with_a_different_key` |
| 5 | Algorithm confusion — re-sign HS256 with the public key as HMAC secret | Refused | `test_handoff_token.py::test_rejects_an_algorithm_confusion_attempt` |
| 6 | Open a `report` link at the `pay` landing | Refused, and the link is **not** spent | `test_handoff_service.py::test_a_token_is_refused_at_the_wrong_landing`, `::test_a_refused_token_is_not_spent` |
| 7 | Claim a different case than the token names | Refused | `test_handoff_token.py::test_a_token_is_scoped_to_one_case` |
| 8 | Invent a fourth intent | Refused | `test_handoff_token.py::test_an_unknown_intent_is_refused_rather_than_coerced` |
| 9 | Read the failure reason to classify a link | One message for every failure | `test_handoff_service.py::test_every_failure_looks_the_same_from_outside` |
| 10 | Use a grant from one link to revive another | Refused | `test_handoff_service.py::test_a_grant_for_another_link_does_not_revive_this_one` |
| 11 | Use an `upload` grant to start a payment | Refused | `test_handoff_grant.py::test_a_grant_for_one_action_does_not_satisfy_another` |
| 12 | Forge a grant cookie | Refused | `test_handoff_grant.py::test_a_forged_grant_is_refused` |
| 13 | Treat completing the action as a login | No session material issued | `test_handoff_token.py::test_is_not_a_session`, `test_handoff_grant.py::test_carries_no_session_material` |
| 14 | Mint a link against someone else's case | Refused at issue | `test_handoff_service.py::test_refuses_to_mint_a_link_to_someone_elses_case` |

## Needs a human against a running stack

- [ ] **Concurrency.** Fire two redemptions of the same token simultaneously from two
      clients. Exactly one must succeed — the unique index on `jti` is the arbiter, and
      this is the one property the mocked ledger in unit tests cannot prove.
- [ ] **Cookie scope in a real browser.** Confirm the grant is not sent to any path
      outside `/api/public/wa/handoff`, survives a reload, and is gone after `release`.
- [ ] **Cross-site arrival.** Confirm the grant survives the actual WhatsApp → browser
      navigation on iOS and Android (this is why it is `SameSite=Lax`, not `Strict`).
- [ ] **Link preview.** Confirm WhatsApp's own preview fetch of a handoff URL does not
      redeem the link. Redemption happens in an effect, not during render, but this must
      be observed against the real client.
- [ ] **Clock skew.** With the server clock moved forward, confirm a token that should
      still be alive is not refused (and vice versa).
- [ ] **Key rotation.** Rotate the RS256 keypair and confirm outstanding links are
      refused rather than accepted or crashing.
- [ ] **Rate limiting.** Confirm the redeem endpoint's limiter engages under a grind, and
      that a legitimate customer retrying twice is not caught by it.
- [ ] **Logs.** Confirm no log line contains a full token, a grant cookie, or a customer
      phone number.

## Known, accepted

- A leaked `pay` link lets a stranger **pay someone else's bill** before it expires. That
  is the accepted trade (D50): no data is disclosed beyond a case reference and an amount,
  card details never touch Veriprops, and payment friction is the cost §7.10 names as the
  channel's most important metric. `upload` and `report` do **not** take this trade —
  they hand off to an authenticated portal instead.
- Outside production, an unconfigured keypair is generated per process, so restarting the
  backend invalidates outstanding links. Production and staging refuse to start that way.

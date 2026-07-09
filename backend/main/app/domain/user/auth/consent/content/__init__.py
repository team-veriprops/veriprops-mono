"""Legal-document content (PRD §3.5).

The seeder upserts each entry into `consent_documents` by (type, consent_version).
Clauses still awaiting counsel sign-off ship as DRAFT; REPORT_DISCLAIMER is FINAL.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from main.app.domain.user.auth.consent.models import (
    ConsentDocumentType,
    ConsentSignoffStatus,
)

_PLATFORM_EFFECTIVE = datetime(2026, 1, 15, tzinfo=timezone.utc)
_VERIFICATION_EFFECTIVE = datetime(2026, 5, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class LegalDocumentContent:
    type: ConsentDocumentType
    consent_version: str
    effective_at: datetime
    title: str
    href: str
    signoff_status: ConsentSignoffStatus
    body: str


_PLATFORM_TERMS = """\
## Platform Terms of Service

These Platform Terms govern your access to and use of the Veriprops platform (the
"Platform"). By creating an account you agree to these Terms.

### 1. The service we provide
Veriprops coordinates independent, vetted agents to verify property information in
Nigeria and produces a structured verification report. **Veriprops reduces
uncertainty; it does not eliminate it.** A report is a professional opinion based on
information available at the time of verification — not a guarantee of title, value,
or fitness, and not legal advice except where a Premium Legal Opinion is expressly
provided by a licensed lawyer (see the Report Disclaimer).

### 2. Merchant of record
Veriprops is the seller of the verification service and the merchant of record.
Payment processors (Paystack/Flutterwave) collect on our behalf; your contract for
the service is with Veriprops.

### 3. Limitation of liability
Veriprops' total aggregate liability to you for any and all claims arising from a
verification is **capped at the total fees you paid for that verification** (the
contractual Naira amount). This cap does **not** limit liability for fraud, wilful
misconduct, death or personal injury, or any liability that cannot lawfully be
excluded or limited.

### 4. Governing law and forum
These Terms are governed by the **laws of Nigeria**, and the **courts of Nigeria**
are the agreed forum for any dispute.

### 5. Your responsibilities
You agree to submit accurate property information, to use the Platform lawfully, and
to keep all communication on the Platform. All communications are recorded for
quality, security, and dispute resolution.

### 6. Changes
We version these Terms. Material changes require your re-acceptance before you
continue; cosmetic changes are acknowledged passively.
"""

_PRIVACY_POLICY = """\
## Privacy Policy

This Policy explains how Veriprops collects, uses, and protects personal data, in
line with the Nigeria Data Protection Act (NDPA).

### 1. What we collect
Account details (name, email, phone), verification inputs you submit, payment
metadata (never full card numbers), device and security-log data (IP, timestamps),
and consent records.

### 2. How we use it
To deliver and improve verification, to prevent fraud, to meet legal obligations,
and to maintain a defensible audit trail. We do not sell your personal data.

### 3. Lawful basis and retention
We process on the basis of contract performance, legitimate interest (fraud
prevention, security), and consent where required. Audit and consent records are
retained for the period required for legal defensibility.

### 4. Your rights (NDPA)
You may access, correct, or request erasure of your personal data. Because audit and
consent records must be retained, an erasure request is fulfilled by
**pseudonymisation**: your identifying data is replaced with a stable opaque token
while the legally necessary event record is preserved.

### 5. Sharing
We share data only with the vetted agents and processors needed to deliver your
verification, and where the law requires.

### 6. Contact
Privacy questions: privacy@veriprops.ng.
"""

_AGENT_TERMS = """\
## Agent Terms

These Terms apply to agents (Field, Registry, Surveyor, and Premium Lawyer roles)
who perform verification tasks on the Platform.

### 1. Independent contractor status
You act as an **independent contractor**, not an employee or agent-in-law of
Veriprops. You are responsible for your own taxes, tools, and professional conduct.

### 2. Professional standards
You will perform tasks competently, truthfully, and within your licence and
competence. The Lawyer role confirms a current NBA licence. You will declare any
conflict of interest per task and confirm property identity on site where required.

### 3. Indemnity
You **indemnify Veriprops** against losses, claims, and costs arising from your
negligence, misconduct, or breach of these Terms. This indemnity is captured as a
versioned attestation.

### 4. Confidentiality and on-platform conduct
Customer information is confidential. All coordination stays on the Platform; sharing
contact details or soliciting off-platform payment is prohibited and monitored.

### 5. Insurance
The professional-indemnity posture for agent roles is being finalised. The Premium
"Legal Opinion" role specifically requires confirmed cover before that tier goes
live.

### 6. Payment
Commission terms, clearance, and reserves are set out at assignment and in the
earnings policy.
"""

_VERIFICATION_TERMS = """\
## Verification Terms

You accept these Terms before payment for a verification. They bundle the clauses
below into a single versioned acceptance.

### 1. Nature of the service
A verification is a professional opinion based on information available at the time,
not a guarantee. **We reduce uncertainty. We do not eliminate it.**

### 2. Limitation of liability
Veriprops' aggregate liability for this verification is **capped at the fees you paid
for it**, with carve-outs for fraud, wilful misconduct, and non-waivable rights (see
Platform Terms §3).

### 3. Refunds
Refund outcomes follow the published Refund & Cancellation Policy. **Refunds are
issued in Naira at the amount paid; your bank converts back at its prevailing rate,
which may differ from your original charge.**

### 4. Jurisdiction
The service is delivered in, and governed by the laws of, **Nigeria**; the courts of
Nigeria are the forum for disputes.

### 5. Communication recording
All communication relating to your verification is recorded and auditable for
quality, security, and dispute resolution.
"""

_REPORT_DISCLAIMER = """\
## Report Disclaimer

This report represents a **professional opinion, not a legal guarantee**. Findings
are based on information available at the time of verification.

Veriprops — Jurisdiction: Nigeria.

*"We reduce uncertainty. We do not eliminate it."*

Where this report includes a Premium Legal Opinion, that opinion is owned and signed
by the individual NBA-licensed lawyer who rendered it; Veriprops transmits it
unaltered and is responsible only for transmission integrity.
"""

_VERIFICATION_DISCLAIMER = """\
## Verification Disclaimer

Before you pay, please understand the limits of what a verification can establish.

A verification confirms what our agents could reasonably observe and obtain from
registries and the site at the time of the work. It cannot detect everything — for
example, undisclosed private arrangements, future events, or records that a registry
does not hold or releases inaccurately.

Where your submitted address or landmark is genuinely ambiguous, our agent verifies
the most defensible interpretation; this is not an error on our part. Where your
input is unambiguous and an agent verifies the wrong property, that is our fault and
is covered by the Refund Policy.

**We reduce uncertainty. We do not eliminate it.**
"""

_FINDINGS_OPINION_ACK = """\
## Findings & Opinion Acknowledgement

You acknowledge the difference between **findings** and **opinion** in your report.

- **Findings** are factual observations and records gathered during verification.
- **An opinion** (including a Premium Legal Opinion) is a professional interpretation
  of those findings.

A Premium Legal Opinion is the work of the individual NBA-licensed lawyer who signs
it. Veriprops transmits that opinion unaltered and warrants only that what you see is
what the lawyer produced — it does not author, own, or guarantee the opinion's
substance. You agree to treat the report as decision-support, not as a substitute for
your own independent judgement.
"""

_JURISDICTION_PLATFORM_ONLY = """\
## Jurisdiction & Platform-Only Transactions

The verification service is provided from **Nigeria** and governed by Nigerian law,
regardless of where you are located.

You agree to keep the entire transaction on the Platform: submission, payment,
communication, and report delivery. Off-platform payments or side agreements with
agents are outside the service, unprotected by these Terms, and prohibited.

The courts of Nigeria are the agreed forum for disputes. Cross-border enforceability
in your home market may vary; this clause's per-market effect is being confirmed.
"""

_COMMUNICATION_RECORDING = """\
## Communication Recording

You consent to the **recording and retention of all communications** on the Platform
relating to your verification — messages with admin, and admin↔agent coordination on
your behalf.

Recording supports quality, fraud prevention, security, and dispute resolution. All
messages are scanned for attempts to share contact or payment details off-platform,
which are blocked. Recorded communications form part of the audit trail and are
retained for legal defensibility, subject to the Privacy Policy.
"""

_REFUND_POLICY = """\
## Refund & Cancellation Policy

Refunds are assessed against the circumstances of your verification. All amounts are
computed from the contractual Naira figure and **issued in Naira through the payment
gateway**; your bank reconverts at its prevailing rate, which may differ from your
original charge.

| Situation | Outcome |
|---|---|
| Cancel before work starts (`IN_PROGRESS`) | Partial refund, less a cancellation surcharge |
| Cancel after work starts | No refund |
| Wrong agent assigned or a step skipped (our fault) | Full refund + free re-verification |
| Registry error or missing public records | No refund; transparent reporting |
| Property inaccessible (with geotagged proof) | Partial refund of the field component |
| Fraudulent customer submission | No refund |
| Payment confirmed but verification never activated | Full refund |
| Ambiguous address you submitted | No refund; re-verification at re-check pricing |
| Wrong property despite your clear input (our fault) | Full refund + free re-verification |

Where a refund is our fault, we may add a goodwill top-up to offset an adverse
reverse-FX gap.
"""


_ENTRIES: list[LegalDocumentContent] = [
    LegalDocumentContent(
        type=ConsentDocumentType.PLATFORM_TERMS, consent_version="1.0.0",
        effective_at=_PLATFORM_EFFECTIVE, title="Platform Terms of Service",
        href="/legal/terms", signoff_status=ConsentSignoffStatus.DRAFT, body=_PLATFORM_TERMS,
    ),
    LegalDocumentContent(
        type=ConsentDocumentType.PRIVACY_POLICY, consent_version="1.0.0",
        effective_at=_PLATFORM_EFFECTIVE, title="Privacy Policy",
        href="/legal/privacy", signoff_status=ConsentSignoffStatus.DRAFT, body=_PRIVACY_POLICY,
    ),
    LegalDocumentContent(
        type=ConsentDocumentType.AGENT_TERMS, consent_version="1.0.0",
        effective_at=_PLATFORM_EFFECTIVE, title="Agent Terms",
        href="/legal/agent-terms", signoff_status=ConsentSignoffStatus.DRAFT, body=_AGENT_TERMS,
    ),
    LegalDocumentContent(
        type=ConsentDocumentType.VERIFICATION_TERMS, consent_version="1.0.0",
        effective_at=_VERIFICATION_EFFECTIVE, title="Verification Terms",
        href="/legal/verification-terms", signoff_status=ConsentSignoffStatus.DRAFT, body=_VERIFICATION_TERMS,
    ),
    LegalDocumentContent(
        type=ConsentDocumentType.REPORT_DISCLAIMER, consent_version="1.0.0",
        effective_at=_PLATFORM_EFFECTIVE, title="Report Disclaimer",
        href="/legal/report-disclaimer", signoff_status=ConsentSignoffStatus.FINAL, body=_REPORT_DISCLAIMER,
    ),
    LegalDocumentContent(
        type=ConsentDocumentType.VERIFICATION_DISCLAIMER, consent_version="1.0.0",
        effective_at=_VERIFICATION_EFFECTIVE, title="Verification Disclaimer",
        href="/legal/verification-disclaimer", signoff_status=ConsentSignoffStatus.DRAFT, body=_VERIFICATION_DISCLAIMER,
    ),
    LegalDocumentContent(
        type=ConsentDocumentType.FINDINGS_OPINION_ACK, consent_version="1.0.0",
        effective_at=_VERIFICATION_EFFECTIVE, title="Findings & Opinion Acknowledgement",
        href="/legal/findings-opinion", signoff_status=ConsentSignoffStatus.DRAFT, body=_FINDINGS_OPINION_ACK,
    ),
    LegalDocumentContent(
        type=ConsentDocumentType.JURISDICTION_PLATFORM_ONLY, consent_version="1.0.0",
        effective_at=_VERIFICATION_EFFECTIVE, title="Jurisdiction & Platform-Only Transactions",
        href="/legal/jurisdiction", signoff_status=ConsentSignoffStatus.DRAFT, body=_JURISDICTION_PLATFORM_ONLY,
    ),
    LegalDocumentContent(
        type=ConsentDocumentType.COMMUNICATION_RECORDING, consent_version="1.0.0",
        effective_at=_VERIFICATION_EFFECTIVE, title="Communication Recording",
        href="/legal/communication-recording", signoff_status=ConsentSignoffStatus.DRAFT, body=_COMMUNICATION_RECORDING,
    ),
    LegalDocumentContent(
        type=ConsentDocumentType.REFUND_POLICY, consent_version="1.0.0",
        effective_at=_VERIFICATION_EFFECTIVE, title="Refund & Cancellation Policy",
        href="/legal/refund-policy", signoff_status=ConsentSignoffStatus.DRAFT, body=_REFUND_POLICY,
    ),
]

# Indexed by document type for seeding and lookup.
LEGAL_DOCUMENT_CONTENT: dict[ConsentDocumentType, LegalDocumentContent] = {
    entry.type: entry for entry in _ENTRIES
}

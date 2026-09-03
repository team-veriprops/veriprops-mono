"""§7.8 WhatsApp clauses in the Platform Terms, Privacy Policy and Communication Recording.

Additive, per decision D49 (`0001_initial_schema` is frozen).

§7.8 asks for four things the committed prose did not say: that WhatsApp is a communication
surface under the §3.5 liability framework, that messages transit Meta infrastructure
outside Nigeria, that the two §7.4.6 opt-ins are separate and withdrawable, and that chat
logs are retained business records held under the same access controls as case data.

**These are new versions, not edits.** The three documents move `1.0.0` → `1.1.0`, which
means every existing account is asked to re-accept before continuing. That is deliberate: a
new cross-border transfer disclosure is a material change under the NDPA, and passing it off
as a cosmetic edit would defeat the purpose of versioning consent at all. `0001`'s own
upsert refreshes the display fields of an existing `(type, consent_version)` and inserts
otherwise, so the `1.0.0` rows stay exactly as they were — they are the evidence of what the
accounts that accepted them were shown.

Retention **duration** is still a counsel sign-off item (§B), so the clauses name the policy
rather than a number, and the three documents stay `DRAFT` until that review lands.

Revision ID: 0011_whatsapp_legal_copy
Revises: 0010_whatsapp_channel_analytics
Create Date: 2026-09-03 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from main.app.domain.user.auth.consent.content import LEGAL_DOCUMENT_CONTENT
from main.app.domain.user.auth.consent.models import ConsentDocumentType
from main.appodus_utils import Utils

# revision identifiers, used by Alembic.
revision: str = "0011_whatsapp_legal_copy"
down_revision: Union[str, None] = "0010_whatsapp_channel_analytics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The documents §7.8 changed. Read from the code registry rather than restated here, for
# the same reason the §7.7 template bodies are code-owned: prose duplicated into a
# migration is prose that can disagree with what the app serves.
_UPDATED_TYPES = (
    ConsentDocumentType.PLATFORM_TERMS,
    ConsentDocumentType.PRIVACY_POLICY,
    ConsentDocumentType.COMMUNICATION_RECORDING,
)


def _rows() -> list[dict]:
    return [
        {
            "type": content.type.value,
            "consent_version": content.consent_version,
            "effective_at": content.effective_at,
            "title": content.title,
            "href": content.href,
            "body": content.body,
            "signoff_status": content.signoff_status.value,
        }
        for document_type in _UPDATED_TYPES
        for content in [LEGAL_DOCUMENT_CONTENT[document_type]]
    ]


def _upsert_legal_documents() -> None:
    """Insert each new version; refresh the display fields if it is already present.

    The same upsert `0001` uses, so a fresh database (which seeds `1.1.0` straight from the
    registry) and a migrated one converge on the same rows.
    """
    conn = op.get_bind()
    now = Utils.datetime_now()
    for row in _rows():
        existing = conn.execute(
            sa.text(
                "SELECT id FROM consent_documents "
                "WHERE type = :type AND consent_version = :consent_version LIMIT 1"
            ),
            {"type": row["type"], "consent_version": row["consent_version"]},
        ).first()
        if existing:
            conn.execute(
                sa.text(
                    "UPDATE consent_documents "
                    "SET title = :title, href = :href, body = :body, "
                    "signoff_status = :signoff_status, date_updated = :now "
                    "WHERE id = :id"
                ),
                {
                    "id": existing[0],
                    "title": row["title"],
                    "href": row["href"],
                    "body": row["body"],
                    "signoff_status": row["signoff_status"],
                    "now": now,
                },
            )
            continue
        conn.execute(
            sa.text(
                "INSERT INTO consent_documents "
                "(id, type, consent_version, effective_at, title, href, body, "
                " signoff_status, date_created, deleted, version) "
                "VALUES (:id, :type, :consent_version, :effective_at, :title, :href, "
                "        :body, :signoff_status, :now, FALSE, 1)"
            ),
            {"id": Utils.generate_uuid(), "now": now, **row},
        )


def upgrade() -> None:
    _upsert_legal_documents()


def downgrade() -> None:
    """Remove the 1.1.0 rows, leaving 1.0.0 as the live version again.

    Acceptances *of* 1.1.0 are deliberately left alone: `user_consents` is the record of
    what a person agreed to, and deleting it because the document was rolled back would
    destroy evidence rather than restore a state.
    """
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM consent_documents "
            "WHERE consent_version = :consent_version AND type = ANY(:types)"
        ),
        {
            "consent_version": "1.1.0",
            "types": [document_type.value for document_type in _UPDATED_TYPES],
        },
    )

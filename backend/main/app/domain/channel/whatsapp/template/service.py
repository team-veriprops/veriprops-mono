"""Meta template registry (PRD §7.7, WA-15/WA-41).

Keeps the app's picture of what Meta will accept in step with Meta's own answer.

Two rules shape everything here:

* **We only track what we declare.** A template registered on the business account that
  this codebase does not declare is not our business — somebody else's experiment, or a
  leftover, and mirroring it would put rows on the launch-gate page that nothing can send.
* **An unreadable status is never optimism.** A declared template Meta has never seen, or
  one whose status we cannot parse, lands as `NOT_FOUND`. Guessing `APPROVED` would let
  the §7.11 gate pass on a template that cannot actually be delivered.

Approval is **advisory at send time** (D59c): it shows up here and on the launch-gate
checklist, and it does not block a send. A sync is a point-in-time snapshot, and a stale
one must not be able to take the channel down.
"""
from __future__ import annotations

from typing import List

from kink import inject

from main.app.domain.channel.whatsapp.template.models import (
    CreateWhatsAppTemplateDto,
    WhatsAppTemplateDto,
    WhatsAppTemplateStatus,
    WhatsAppTemplateSyncResultDto,
)
from main.app.domain.channel.whatsapp.template.repo import WhatsAppTemplateRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.integrations.messaging.providers.whatsapp.directory import (
    whatsapp_template_directory,
)
from main.appodus_utils.integrations.messaging.templating.whatsapp_templates import (
    declared_templates,
)


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WhatsAppTemplateService:
    def __init__(self, whatsapp_template_repo: WhatsAppTemplateRepo):
        self._whatsapp_template_repo = whatsapp_template_repo

    async def list_all(self) -> List[WhatsAppTemplateDto]:
        """The §7.7 set, as the admin registry renders it.

        Driven by the **declarations**, not by the table: a template declared but never
        synced still has to appear, because "we have not submitted this yet" is the state
        the launch gate most needs to show.
        """
        rows = {row.name: row for row in await self._whatsapp_template_repo.list_all()}
        registry: List[WhatsAppTemplateDto] = []

        for declaration in declared_templates():
            row = rows.get(declaration.name)
            registry.append(WhatsAppTemplateDto(
                name=declaration.name,
                category=declaration.category.value,
                language=declaration.language,
                status=(
                    WhatsAppTemplateStatus(row.status) if row
                    else WhatsAppTemplateStatus.NOT_FOUND
                ),
                rejection_reason=row.rejection_reason if row else None,
                last_synced_at=row.last_synced_at if row else None,
                parameters=[p.value for p in declaration.parameters],
            ))
        return registry

    async def sync(self) -> WhatsAppTemplateSyncResultDto:
        """Pull every declared template's status from the configured directory."""
        remote = {t.name: t for t in await whatsapp_template_directory().list_templates()}
        now = Utils.datetime_now()
        approved = 0
        missing = 0

        for declaration in declared_templates():
            match = remote.get(declaration.name)
            status = (
                WhatsAppTemplateStatus.from_meta(match.status) if match
                else WhatsAppTemplateStatus.NOT_FOUND
            )
            if status == WhatsAppTemplateStatus.APPROVED:
                approved += 1
            if match is None:
                missing += 1

            row = await self._whatsapp_template_repo.get_by_name(declaration.name)
            if row is None:
                row = await self._whatsapp_template_repo.create_return_model(
                    CreateWhatsAppTemplateDto(
                        name=declaration.name,
                        category=declaration.category.value,
                        language=declaration.language,
                        status=status,
                        remote_id=match.remote_id if match else None,
                        rejection_reason=match.rejection_reason if match else None,
                    )
                )
                # `create` cannot carry the timestamp (the update path stringifies
                # datetimes), so it is set on the attached row here.
                row.last_synced_at = now
                self._whatsapp_template_repo._session.add(row)
            else:
                self._whatsapp_template_repo.apply_remote_state(
                    row,
                    status,
                    match.remote_id if match else None,
                    match.rejection_reason if match else None,
                    now,
                )

        return WhatsAppTemplateSyncResultDto(
            synced=len(declared_templates()), approved=approved, missing=missing
        )

    async def is_approved(self, template_name: str) -> bool:
        """Whether Meta has approved *template_name*, as of the last sync.

        Advisory (D59c) — read by the launch-gate view, never by the send path. A stale
        snapshot must not be able to stop a message the customer is waiting for.
        """
        row = await self._whatsapp_template_repo.get_by_name(template_name)
        return bool(row and row.status == WhatsAppTemplateStatus.APPROVED.value)

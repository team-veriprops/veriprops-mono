"""Agent application business-rule validation (PRD §3.1)."""
from kink import inject

from main.app.core.state.status import AgentRole
from main.app.domain.user.agent.models import (
    ROLE_REQUIRED_CREDENTIAL,
    SubmitAgentApplicationDto,
)
from main.appodus_utils.exception.exceptions import ValidationException


@inject
class AgentApplicationValidator:
    def validate_submission(self, dto: SubmitAgentApplicationDto) -> None:
        if not dto.roles:
            raise ValidationException(message="Pick at least one role to apply for.")

        if not dto.truthfulness_confirmed:
            raise ValidationException(message="You must confirm the information is truthful.")

        if not dto.agent_terms_version:
            raise ValidationException(message="Agent Terms must be accepted.")

        # Conditional credentials: a role that requires a professional licence
        # (Surveyor, Lawyer) must have a matching credential in the submission.
        credential_roles = {c.role for c in dto.credentials}
        for role in dto.roles:
            required = ROLE_REQUIRED_CREDENTIAL.get(role)
            if required is not None and role not in credential_roles:
                raise ValidationException(
                    message=f"The {role.value} role requires a {required.value} credential.",
                )

        # Each supplied credential must match the role it claims to back.
        for cred in dto.credentials:
            expected = ROLE_REQUIRED_CREDENTIAL.get(cred.role)
            if expected is not None and cred.credential_type != expected:
                raise ValidationException(
                    message=f"{cred.role.value} requires {expected.value}, not {cred.credential_type.value}.",
                )

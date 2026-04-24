import enum
from enum import Enum
from typing import Optional, List

from pydantic import field_validator, Field, ConfigDict

from main.appodus_utils import Object




class SignActionType(str, Enum):
    VIEW = "VIEW"
    SIGN = "SIGN"
    APPROVER = "APPROVER"

class DocumentVerificationType(str, enum.Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    OFFLINE = "OFFLINE"

class SignRequestResponseDto(Object):
    request_id: str
    signers: List['Signer']
    final_contract_id: Optional[str] = None

class Signer(Object):
    """
    Represents a signer in a Zoho Sign document request.

    Attributes:
        recipient_email: Valid email address of the signer
        recipient_name: Full name of the signer
        role: Role description (e.g., "Client", "Manager")
        action_type: Type of action required (SIGN/APPROVER/VIEW)
        signing_order: Optional order in signing sequence (1-based)
    """
    action_id: Optional[str] = Field(None, description="The returned action ID on a successful request")
    action_type: SignActionType = Field(SignActionType.SIGN, description="Required action from signer")
    recipient_email: str = Field(..., description="Signer's email address")
    recipient_phonenumber: Optional[str] = Field(None, description="Signer's phone number")
    recipient_name: str = Field(..., min_length=1, max_length=100, description="Signer's full name")
    verify_recipient: bool = Field(True)
    verification_type: Optional[DocumentVerificationType] = Field(DocumentVerificationType.EMAIL)
    verification_code: Optional[str] = Field(None, description="Verification Code required on in case of OFFLINE Verification type")
    private_notes: Optional[str] = Field(None, description="Private notes for a recipient")
    is_embedded: Optional[bool] = Field(False, description="Whether this request will be embedded, and not sent directly to the signer")
    signing_order: Optional[int] = Field(
        None,
        ge=-1,
        le=20,
        description="Order in signing sequence (1-based index)"
    )

    @field_validator('recipient_name')
    def recipient_name_must_contain_space(cls, v):
        if ' ' not in v.strip():
            raise ValueError("Name must contain at least first and last name")
        return v.title()

    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "recipient_email": "signer1@example.com",
                "recipient_name": "John Doe",
                "action_type": "SIGN",
                "signing_order": 1
            }
        }
    )

# # Example Usage
# signer_data = {
#     "email": "signer1@example.com",
#     "name": "John Doe",
#     "role": "Signer 1",
#     "action_type": "SIGN"
# }
#
# signer = Signer(**signer_data)
# print(signer.model_dump_json(indent=2))

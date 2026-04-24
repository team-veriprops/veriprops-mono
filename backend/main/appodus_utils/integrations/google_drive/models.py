from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict, Literal
from enum import Enum


class ResourceState(str, Enum):
    SYNC = "sync"
    UPDATE = "update"
    ADD = "add"
    TRASH = "trash"
    UNTRASH = "untrash"
    REMOVE = "remove"


class ChangeType(str, Enum):
    FILE = "file"
    DRIVE = "drive"
    TEAM_DRIVE = "teamDrive"


class GoogleDriveWebhookPayload(BaseModel):
    """
    Full model for Google Drive webhook notifications.
    Reference: https://developers.google.com/drive/api/v3/push
    """
    # Required fields
    kind: Literal["api#channel"] = Field(..., description="Identifies this as a notification channel")
    id: str = Field(..., min_length=1, max_length=256,
                    description="UUID identifying this notification channel")
    resourceId: str = Field(..., description="Opaque ID of the watched resource")
    resourceUri: HttpUrl = Field(..., description="Version-specific ID of the watched resource")
    resourceState: ResourceState = Field(..., description="Current state of the resource")

    # Optional fields (present depending on event type)
    channelId: Optional[str] = Field(None, description="Notification channel UUID")
    expiration: Optional[datetime] = Field(None, description="When this notification channel expires")
    changed: Optional[datetime] = Field(None, description="When the change occurred (RFC 3339 format)")

    # File-specific fields (when resource is a file)
    fileId: Optional[str] = Field(None, description="The ID of the file that changed")
    driveId: Optional[str] = Field(None, description="The ID of the shared drive")
    type: Optional[ChangeType] = Field(None, description="Type of the changed resource")

    # Additional metadata
    token: Optional[str] = Field(None, description="Opaque value used by some Drive APIs")
    userToken: Optional[str] = Field(None, description="Opaque value set by client apps")
    startPageToken: Optional[str] = Field(None, description="Starting pageToken for change events")

    # Webhook security headers (should be validated separately)
    headers: Optional[Dict[str, str]] = Field(
        None,
        description="Security headers from the webhook request",
        examples=[
            {
                "X-Goog-Resource-State": "update",
                "X-Goog-Channel-ID": "channel-123",
                "X-Goog-Message-Number": "123456",
                "X-Goog-Resource-URI": "https://www.googleapis.com/drive/v3/files/abc123",
                "X-Goog-Resource-ID": "abc123",
                "X-Goog-Changed": "content,properties",
                "X-Goog-Signature": "abc123...",  # Present if using verification secret
                "X-Goog-Verification-Token": "..."  # Present if using verification token
            }
        ]
    )

    # For batch notifications
    changes: Optional[List[Dict]] = Field(
        None,
        description="For batch notifications, contains multiple changes",
        examples=[{
            "type": "file",
            "fileId": "abc123",
            "changeType": "update"
        }]
    )

    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "kind": "api#channel",
                "id": "channel-123",
                "resourceId": "abc123",
                "resourceUri": "https://www.googleapis.com/drive/v3/files/abc123",
                "resourceState": "update",
                "fileId": "abc123",
                "driveId": "drive-123",
                "changed": "2023-07-25T12:00:00Z",
                "headers": {
                    "X-Goog-Resource-State": "update",
                    "X-Goog-Channel-ID": "channel-123"
                }
            }
        }
    )

    def is_sync_notification(self) -> bool:
        """Check if this is just a sync ping (no real change)"""
        return self.resourceState == ResourceState.SYNC

    def is_update_notification(self) -> bool:
        return self.resourceState == ResourceState.UPDATE

    def get_changed_fields(self) -> Optional[List[str]]:
        """Extract changed fields from headers if available"""
        if not self.headers:
            return None
        changed = self.headers.get("X-Goog-Changed")
        return changed.split(",") if changed else None

import mimetypes
from pathlib import Path
from typing import List, Dict, Any, Optional

from pydantic import Field, field_validator

from main.appodus_utils import Object
from main.appodus_utils import Base64Utils, Utils

# Constants
CHUNK_SIZE = 64 * 1024  # 64 KB for streaming
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB max per attachment


class EmailValidationError(ValueError):
    pass


class Attachment(Object):
    content_type: str = Field(default="application/octet-stream", description="MIME type of the attachment")
    filename: str = Field(..., description="Name of the attached file")
    content: str = Field(..., description="Base64 encoded content of the attachment")


class EmailResponse(Object):
    """
        Model representing the response structure of an email content.

        Attributes:
            subject (str): Email subject line.
            html (str): Optional HTML content.
            text (str): Plain text fallback content.
            from_email (str): Sender's email address.
            from_name (str): Sender's display name.
            template_id (int): ID of the email template (if used).
            variables (dict): Variables for the template (if used).
            attachments (List[Attachment]): List of attachments added to the email.
        """
    subject: str
    html: Optional[str] = None
    text: str = ""
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    template_id: Optional[int] = None
    variables: Optional[Dict[str, Any]] = None
    attachments: List[Attachment] = []


class AttachmentRequest(Object):
    """
        Input model for specifying a file to be attached to an email.

        Attributes:
            file_path (Path): Path to the file on the filesystem.
            filename (Optional[str]): Optional override for the file's name in the email.
            content_type (Optional[str]): Optional override for the file's MIME type.
        """

    file_path: Path
    filename: Optional[str] = None
    content_type: Optional[str] = None

    @field_validator('file_path')
    def check_file_exists(cls, value: Path):
        """Ensure the file exists before processing."""
        if not value.exists():
            raise ValueError(f"File not found: {value}")
        return value


class EmailContentBuilder:
    """
    A builder for constructing email content with attachments.

    This class allows users to set email subject, body content (text and/or HTML),
    sender information, and attachments. The builder can handle file size validation,
    Base64 encoding of attachments, and dynamic email templates.

    Example Usage:
        email_builder = EmailContentBuilder()
        email = (email_builder.with_subject("Test Email")
                            .with_text_content("This is a plain-text email.")
                            .with_html_content("<p>This is an HTML email.</p>")
                            .with_from_email("sender@example.com")
                            .with_from_name("Sender Name")
                            .add_attachment(AttachmentRequest(file_path=Path("path/to/file")))
                            .build())
        print(email)
    """

    def __init__(self):
        self._subject = None
        self._html = None
        self._text = ""
        self._from_email = None
        self._from_name = None
        self._template_id = None
        self._variables = None
        self._attachments = []

    def with_subject(self, subject: str):
        self._subject = subject
        return self

    def with_html_content(self, html: str):
        self._html = html
        return self

    def with_text_content(self, text: str):
        self._text = text
        return self

    def with_from_email(self, from_email: str):
        self._from_email = from_email
        return self

    def with_from_name(self, from_name: str):
        self._from_name = from_name
        return self

    def with_template(self, template_id: int, variables: dict):
        self._template_id = template_id
        self._variables = variables
        return self

    def add_attachment(self, attachment: AttachmentRequest):
        self._attachments.append(attachment)
        return self

    def build(self) -> EmailResponse:
        if not self._subject:
            raise ValueError("Subject is required")
        if not (self._html or self._text or self._template_id):
            raise ValueError("Either content or template must be provided")

        email_data = {
            "subject": self._subject,
            "html": self._html,
            "text": self._text,
            "from_email": self._from_email,
            "from_name": self._from_name,
            "template_id": self._template_id,
            "variables": self._variables,
            "attachments": [],
        }

        if self._template_id:
            # Template-based email
            email = EmailResponse(**email_data)
        else:
            # Content-based email
            email = EmailResponse(**email_data)

        if self._attachments:
            self.add_attachments(email, self._attachments)

        return email

    @staticmethod
    def add_attachments(content: EmailResponse, payloads: List[AttachmentRequest]):
        attachments = []
        for payload in payloads:
            if not payload.file_path.exists():
                raise FileNotFoundError(f"File not found: {payload.file_path}")

            # Validate file size
            Utils.validate_file_size(payload.file_path, MAX_ATTACHMENT_SIZE)

            # Encode file
            encoded_content = Base64Utils.file_path_to_base64(payload.file_path)

            filename = payload.filename or payload.file_path.name
            content_type = payload.content_type
            if not content_type:
                guessed_type, _ = mimetypes.guess_type(payload.file_path)
                content_type = guessed_type or "application/octet-stream"

            attachment = Attachment(
                content_type=content_type,
                filename=filename,
                content=encoded_content,
            )
            attachments.append(attachment)

        content.attachments = attachments

        return content

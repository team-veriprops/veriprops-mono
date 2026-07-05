"""CamelModel UUID coercion — hand-built DTOs (``id=entity.id``) must accept raw UUIDs.

Regression for the 500 on ``GET /api/users/admins/team``: a DTO with a ``str`` id field
built from a real ``uuid.UUID`` used to raise ``string_type``.
"""
import uuid

from main.appodus_utils.db.models import Object


class _SampleDto(Object):
    id: str
    name: str


class TestUuidCoercion:
    def test_raw_uuid_id_becomes_hex_string(self):
        raw = uuid.uuid4()
        dto = _SampleDto(id=raw, name="Ada")
        assert dto.id == raw.hex
        assert isinstance(dto.id, str)
        assert "-" not in dto.id  # hex form, matches Utils.uuid_to_hex

    def test_string_id_passes_through_unchanged(self):
        dto = _SampleDto(id="already-a-string", name="Ada")
        assert dto.id == "already-a-string"

    def test_camel_case_serialization_still_applies(self):
        raw = uuid.uuid4()
        dto = _SampleDto(id=raw, name="Ada")
        assert dto.model_dump(by_alias=True)["id"] == raw.hex

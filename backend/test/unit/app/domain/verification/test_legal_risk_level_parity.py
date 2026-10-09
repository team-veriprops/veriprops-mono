"""The frontend's LegalRiskLevel enum mirrors the backend's, member for member.

The lawyer's form offers exactly these values as its risk-level choices, and the validator
refuses anything else, so a level added on one side alone would either never be offered or
be refused on submit. This pins the two together, in both directions.
"""
import re
from pathlib import Path

from main.app.domain.verification.task.models import LegalRiskLevel

_FRONTEND_TYPES = Path(__file__).resolve().parents[6] / "frontend" / "src" / "types" / "agentTask.ts"
_MEMBER = re.compile(r'^\s*([A-Z0-9_]+)\s*=\s*"([A-Z0-9_]+)",?\s*$', re.MULTILINE)


def _frontend_levels() -> dict[str, str]:
    source = _FRONTEND_TYPES.read_text(encoding="utf-8")
    body = source[source.index("export enum LegalRiskLevel"):]
    body = body[: body.index("}")]
    return dict(_MEMBER.findall(body))


def test_the_frontend_enum_mirrors_every_backend_level():
    frontend = _frontend_levels()
    assert frontend, "no LegalRiskLevel members parsed from agentTask.ts"
    assert frontend == {level.name: level.value for level in LegalRiskLevel}

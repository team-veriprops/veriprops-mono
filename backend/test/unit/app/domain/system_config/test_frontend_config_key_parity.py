"""The frontend's ConfigKey enum mirrors the backend's, key for key.

The admin settings page renders whatever keys the backend lists, but typed frontend code refers to
keys through `frontend/src/types/systemConfig.ts`. That enum had drifted to 3 of the backend's
keys; this pins the two together, in both directions, so a key added on one side fails CI until
the other side has it too.
"""
import re
from pathlib import Path

from main.app.domain.system_config.models import ConfigKey

_FRONTEND_TYPES = Path(__file__).resolve().parents[6] / "frontend" / "src" / "types" / "systemConfig.ts"
_MEMBER = re.compile(r'^\s*([A-Z0-9_]+)\s*=\s*"([a-z0-9_]+)",?\s*$', re.MULTILINE)


def _frontend_keys() -> dict[str, str]:
    source = _FRONTEND_TYPES.read_text(encoding="utf-8")
    body = source[source.index("export enum ConfigKey"):]
    body = body[: body.index("}")]
    return dict(_MEMBER.findall(body))


def test_the_frontend_enum_mirrors_every_backend_config_key():
    frontend = _frontend_keys()
    assert frontend, "no ConfigKey members parsed from systemConfig.ts"
    assert frontend == {key.name: key.value for key in ConfigKey}

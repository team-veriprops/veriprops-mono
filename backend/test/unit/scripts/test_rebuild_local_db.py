"""`scripts/rebuild_local_db.py` — rebuilding a local database a squash left behind.

A database recorded at a revision the squash removed can't be upgraded (alembic can't find the
revision), and stamping it at the new head would claim migrations it never ran. So it is dropped
and rebuilt. Dropping is destructive, so the guards are what is tested: only the known local
databases, never under a staging/production environment, and nothing without an explicit `--yes`.
"""
import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "rebuild_local_db.py"


def _module():
    spec = importlib.util.spec_from_file_location("rebuild_local_db", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", ["veriprops_test", "veriprops_local", "veriprops_e2e", "veriprops_uat"])
def test_the_local_databases_are_allowed(name):
    _module().check_target(name, active_env="dev_personal")


@pytest.mark.parametrize("name", [
    "veriprops", "veriprops_prod", "postgres", "veriprops_test; DROP DATABASE veriprops", "VERIPROPS_TEST",
])
def test_anything_else_is_refused(name):
    module = _module()
    with pytest.raises(module.RefusedTarget):
        module.check_target(name, active_env="dev_personal")


@pytest.mark.parametrize("env", ["staging", "prod"])
def test_a_deployed_environment_is_refused(env):
    module = _module()
    with pytest.raises(module.RefusedTarget):
        module.check_target("veriprops_test", active_env=env)


def test_without_yes_it_only_says_what_it_would_do(monkeypatch, capsys):
    module = _module()
    ran = []
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: ran.append(a))
    monkeypatch.setenv("APPODUS_ACTIVE_ENV", "test")

    assert module.main(["veriprops_test"]) == 0

    assert ran == []
    assert "--yes" in capsys.readouterr().out


def test_with_yes_it_recreates_then_migrates(monkeypatch):
    module = _module()
    commands = []

    class _Done:
        returncode = 0

    def _run(cmd, **kwargs):
        commands.append((cmd, (kwargs.get("env") or {}).get("DB_NAME")))
        return _Done()

    monkeypatch.setattr(module.subprocess, "run", _run)
    monkeypatch.setenv("APPODUS_ACTIVE_ENV", "test")

    assert module.main(["veriprops_test", "--yes"]) == 0

    psql, alembic = commands
    assert "DROP DATABASE IF EXISTS veriprops_test WITH (FORCE)" in " ".join(psql[0])
    assert "CREATE DATABASE veriprops_test" in " ".join(psql[0])
    assert alembic[0][-3:] == ["alembic", "upgrade", "head"]
    assert alembic[1] == "veriprops_test"

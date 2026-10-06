"""POST /internal/sweeps/tick — the Cloudflare Cron Worker's door to the sweeps.

It carries no session: the caller is a Worker, authorised by `SWEEP_TRIGGER_SECRET` in the
`x-sweep-secret` header, compared in constant time. An environment without the secret has the
door **disabled, never open**: it answers 404, as if the route did not exist.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from main.app.config.settings import settings
from main.app.domain.scheduled_job import controller as controller_mod
from main.app.domain.scheduled_job.models import SweepJobOutcome, SweepJobResultDto, SweepTickResultDto
from main.app.jobs import tick as tick_mod
from veriprops import app as real_app

_SECRET = "a-strong-sweep-secret"
_PATH = "/api/internal/sweeps/tick"


@pytest.fixture
def ticks(monkeypatch):
    calls = []

    async def _fake_tick():
        calls.append(True)
        return SweepTickResultDto(jobs=[
            SweepJobResultDto(name="message_retry_check", outcome=SweepJobOutcome.RAN, duration_ms=12),
        ])

    monkeypatch.setattr(tick_mod, "run_sweep_tick", _fake_tick)
    return calls


@pytest.fixture
def client():
    app = FastAPI(exception_handlers=real_app.exception_handlers)
    app.router.routes.extend(real_app.router.routes)
    return TestClient(app, raise_server_exceptions=False)


def _post(client, secret=None):
    headers = {} if secret is None else {settings.SWEEP_TRIGGER_HEADER: secret}
    return client.post(_PATH, headers=headers)


@pytest.mark.parametrize("configured", ["", "CHANGE_ME"])
def test_without_a_configured_secret_the_door_does_not_exist(monkeypatch, client, ticks, configured):
    monkeypatch.setattr(settings, "SWEEP_TRIGGER_SECRET", configured)

    # Not even a caller who guesses the placeholder gets in.
    assert _post(client, configured).status_code == 404
    assert _post(client).status_code == 404
    assert ticks == []


@pytest.mark.parametrize("supplied", [None, "", "wrong", _SECRET + "x"])
def test_a_missing_or_wrong_secret_is_refused(monkeypatch, client, ticks, supplied):
    monkeypatch.setattr(settings, "SWEEP_TRIGGER_SECRET", _SECRET)

    assert _post(client, supplied).status_code == 401
    assert ticks == []


def test_the_right_secret_runs_one_tick_and_returns_its_summary(monkeypatch, client, ticks):
    monkeypatch.setattr(settings, "SWEEP_TRIGGER_SECRET", _SECRET)

    response = _post(client, _SECRET)

    assert response.status_code == 200
    assert ticks == [True]
    assert response.json()["data"]["jobs"] == [
        {"name": "message_retry_check", "outcome": "RAN", "durationMs": 12},
    ]


def test_the_comparison_is_constant_time():
    import inspect
    assert "compare_digest" in inspect.getsource(controller_mod)

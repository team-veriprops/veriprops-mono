"""EdgeAuthMiddleware — trusted-edge (Cloudflare) header enforcement.

The middleware closes the direct-origin bypass: when a secret is configured, only
requests carrying the header the Cloudflare Transform Rule injects may reach the
app. Blank/placeholder secrets disable the check so local/test/e2e run open.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from main.appodus_utils.config.settings import SECRET_PLACEHOLDER
from main.appodus_utils.middleware.edge_auth_middleware import EdgeAuthMiddleware

HEADER = "x-edge-auth"
SECRET = "test-edge-secret-value"


def _client(secret: str) -> TestClient:
    app = FastAPI()
    app.add_middleware(EdgeAuthMiddleware, secret=secret, header_name=HEADER)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return TestClient(app)


class TestDisabled:
    def test_empty_secret_leaves_requests_open(self):
        assert _client("").get("/ping").status_code == 200

    def test_whitespace_secret_leaves_requests_open(self):
        assert _client("   ").get("/ping").status_code == 200

    def test_placeholder_secret_leaves_requests_open(self):
        assert _client(SECRET_PLACEHOLDER).get("/ping").status_code == 200


class TestEnforced:
    def test_missing_header_is_rejected(self):
        response = _client(SECRET).get("/ping")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "EDGE_AUTH_REQUIRED"

    def test_wrong_header_value_is_rejected(self):
        response = _client(SECRET).get("/ping", headers={HEADER: "wrong-value"})
        assert response.status_code == 403

    def test_correct_header_passes(self):
        response = _client(SECRET).get("/ping", headers={HEADER: SECRET})
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_header_name_is_case_insensitive(self):
        response = _client(SECRET).get("/ping", headers={"X-Edge-Auth": SECRET})
        assert response.status_code == 200

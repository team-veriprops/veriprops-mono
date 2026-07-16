"""Root pytest conftest — bootstraps the environment so domain modules can
import without ValueError on unset env vars. The env file is selected via
`appodus_active_env` (default 'test')."""
import os

# Default to the inert test env (.env.test: throwaway localhost DB, scheduler
# off, all stubs on, zero secrets) so a plain `pytest` runs under the test-env
# policy. Export appodus_active_env explicitly to target another env file.
os.environ.setdefault("appodus_active_env", "test")

# Importing the settings module triggers `set_env_vars()` which populates
# os.environ from `.env.{appodus_active_env}` — required before any module
# that reads env vars at import time (logger, db.session, etc.).
from main.app.config import settings as _settings  # noqa: F401, E402
from main.app.config.bootstrap import DiBootstrap  # noqa: F401, E402

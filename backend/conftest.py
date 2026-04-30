"""Root pytest conftest — bootstraps the environment so domain modules can
import without ValueError on unset env vars. The env file is selected via
`appodus_active_env` (default 'local')."""
import os

# Default to local env if the developer didn't export it.
os.environ.setdefault("appodus_active_env", "local")

# Importing the settings module triggers `set_env_vars()` which populates
# os.environ from `.env.{appodus_active_env}` — required before any module
# that reads env vars at import time (logger, db.session, etc.).
from main.app.config import settings as _settings  # noqa: F401, E402
from main.app.config.bootstrap import DiBootstrap  # noqa: F401, E402

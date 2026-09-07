"""WhatsApp channel analytics (PRD §26.10, WA-43).

The §26.10 facts (`models.py`, written by `recorder.py`) and Meta's number health
(`health_service.py`). The **read** surface deliberately lives elsewhere: `AnalyticsService`
in `app/domain/analytics/` aggregates these rows alongside every other admin metric, so the
admin API stays one router behind one permission guard (D86).

Imported by the channel package so Alembic sees both tables.
"""
from main.app.domain.channel.whatsapp.analytics import models  # noqa: F401

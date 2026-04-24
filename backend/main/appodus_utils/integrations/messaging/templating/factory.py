from main.app.config.settings import settings
from main.appodus_utils.integrations.messaging.templating.adapters.jinja2 import Jinja2EngineFactory
from main.appodus_utils.integrations.messaging.templating.engine import TemplateEngineFactory


def get_template_engine_factory() -> TemplateEngineFactory:
    """Return the configured template engine factory"""
    engine_type = settings.TEMPLATE_ENGINE.lower()

    if engine_type == "jinja2":
        return Jinja2EngineFactory()
    else:
        raise ValueError(f"Unsupported template engine: {engine_type}")

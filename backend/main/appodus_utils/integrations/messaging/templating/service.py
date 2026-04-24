from typing import Dict, Any

from kink import inject

from main.appodus_utils.exception.exceptions import TemplateRenderingException
from main.appodus_utils.integrations.messaging.models import MessageChannel
from main.appodus_utils.integrations.messaging.templating.engine import TemplateEngine
from main.appodus_utils.integrations.messaging.templating.factory import get_template_engine_factory
from main.appodus_utils.integrations.messaging.templating.models import AvailableTemplate


@inject
class TemplateService:
    def __init__(self):
        self.engine_factory = get_template_engine_factory()
        self._engine = None

    @property
    def engine(self) -> TemplateEngine:
        """Lazy-load the engine instance"""
        if self._engine is None:
            self._engine = self.engine_factory.create_engine()
        return self._engine

    async def render_message(
            self,
            channel: MessageChannel,
            template_name: AvailableTemplate,
            context: Dict[str, Any]
    ) -> str:
        full_template_path = f"{channel.value}/{template_name.value}.{self.engine_factory.template_extension}"

        try:
            if not self.engine.supports_template(full_template_path):
                raise TemplateRenderingException(f"Template not found: {full_template_path}")

            return self.engine.render(full_template_path, context)
        except ValueError as e:
            raise TemplateRenderingException(str(e))

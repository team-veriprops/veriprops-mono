from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    from loguru import Logger

from kink import di, inject

from main.appodus_utils.exception.exceptions import TemplateRenderingException
from main.appodus_utils.integrations.messaging.models import MessageChannel
from main.appodus_utils.integrations.messaging.templating.engine import TemplateEngine
from main.appodus_utils.integrations.messaging.templating.factory import get_template_engine_factory
from main.appodus_utils.integrations.messaging.templating.models import AvailableTemplate

logger: Logger = di["logger"]


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
        full_template_path = Path(channel.value, f"{template_name.value}.{self.engine_factory.template_extension}").as_posix()

        # A rendering failure is a 422, whose message reaches the client — so the template path
        # and the engine's own error are logged here and the exception keeps its generic text.
        if not self.engine.supports_template(full_template_path):
            logger.error(f"Template not found: {full_template_path}")
            raise TemplateRenderingException()

        try:
            return self.engine.render(full_template_path, context)
        except ValueError as e:
            logger.error(f"Template {full_template_path} failed to render: {e}")
            raise TemplateRenderingException() from e

from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    from loguru import Logger

from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from kink import di

from main.app.config.settings import settings
from main.appodus_utils.exception.exceptions import TemplateRenderingException
from main.appodus_utils.integrations.messaging.templating.engine import TemplateEngine, TemplateEngineFactory

logger: Logger = di["logger"]


class Jinja2TemplateEngine(TemplateEngine):
    def __init__(self, template_dir: Path):
        self.template_dir = template_dir
        self.env = self._create_environment()

        super().__init__()

    def _create_environment(self) -> Environment:
        return Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render a template with the given context.
        """
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        # The exception is a 422 whose message reaches the client: the template name and Jinja's
        # own error go to the log, and the exception keeps its generic text.
        except TemplateNotFound as e:
            logger.error(f"Template not found: {template_name}")
            raise TemplateRenderingException() from e
        except Exception as e:
            logger.error(f"Template {template_name} failed to render: {e}")
            raise TemplateRenderingException() from e

    def supports_template(self, template_name: str) -> bool:
        """
        Check if the specified template is available in the environment.
        """
        try:
            self.env.get_template(template_name)
            return True
        except TemplateNotFound:
            return False


class Jinja2EngineFactory(TemplateEngineFactory):
    def __init__(self):
        self.template_dir = self._get_template_dir()

    @property
    def template_extension(self) -> str:
        return "jinja2"

    def create_engine(self) -> TemplateEngine:
        return Jinja2TemplateEngine(template_dir=self.template_dir)

    @staticmethod
    def _get_template_dir():
        base_dir = Path(settings.BASE_DIR).resolve(strict=True)

        template_dir = (
            base_dir
            .joinpath("integrations", "messaging", "templates")
            .resolve(strict=True)
        )

        if not template_dir.is_dir():
            raise NotADirectoryError(f"Invalid template directory: {template_dir}")

        if base_dir not in template_dir.parents and template_dir != base_dir:
            raise ValueError("Template directory escapes BASE_DIR")

        return template_dir


from typing import Dict, Any

from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from main.app.config.settings import settings
from main.appodus_utils.exception.exceptions import TemplateRenderingException
from main.appodus_utils.integrations.messaging.templating.engine import TemplateEngine, TemplateEngineFactory


class Jinja2TemplateEngine(TemplateEngine):
    def __init__(self, template_dir: str):
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
        except TemplateNotFound:
            raise TemplateRenderingException(f"Template not found: {template_name}")
        except Exception as e:
            raise TemplateRenderingException(f"Template rendering failed: {str(e)}")

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
        self.template_dir = Path(settings.BASE_DIR) / "app/templates"

    @property
    def template_extension(self) -> str:
        return "jinja2"

    def create_engine(self) -> TemplateEngine:
        return Jinja2TemplateEngine(template_dir=self.template_dir)

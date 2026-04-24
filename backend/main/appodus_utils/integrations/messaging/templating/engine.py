from abc import abstractmethod, ABC
from typing import Dict, Any


class TemplateEngine(ABC):
    """Abstract base class for all template engines"""

    @abstractmethod
    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a template with the given context"""
        pass

    @abstractmethod
    def supports_template(self, template_name: str) -> bool:
        """Check if template exists in the engine"""
        pass


class TemplateEngineFactory(ABC):
    """Abstract factory for creating template engines"""

    @property
    @abstractmethod
    def template_extension(self) -> str:
        """File extension for templates used by this engine"""
        pass

    @abstractmethod
    def create_engine(self) -> TemplateEngine:
        """Create a new instance of the template engine"""
        pass

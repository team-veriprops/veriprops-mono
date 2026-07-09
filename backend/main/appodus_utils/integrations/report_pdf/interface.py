from abc import ABC, abstractmethod

from main.appodus_utils.integrations.report_pdf.models import ReportPdfContext


class IReportPdfProvider(ABC):
    """Renders a released report into PDF bytes (§10.1). Implementations must put the
    legal footer on every page (§10.2)."""

    @property
    @abstractmethod
    def platform(self) -> str:
        ...

    @abstractmethod
    def render(self, context: ReportPdfContext) -> bytes:
        ...

"""Re-export SuccessResponse from db.models for backward-compat imports."""
from main.appodus_utils.db.models import SuccessResponse  # noqa: F401

__all__ = ["SuccessResponse"]

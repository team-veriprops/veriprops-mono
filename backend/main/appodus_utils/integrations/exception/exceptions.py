from datetime import datetime

from main.appodus_utils.exception.exceptions import AppodusBaseException


class IntegrationException(AppodusBaseException):
    """Integration exception"""
    def __init__(self, message: str, visible: bool = False):
        self.message = f"{message}"
        self.visible = visible


class IntegrationInsufficientBalanceException(IntegrationException):
    """Integration Insufficient balance exception"""
    pass


class IntegrationAuthenticationException(IntegrationException):
    """Integration Authentication exception"""
    pass


class IntegrationRateLimitException(IntegrationException):
    def __init__(self, key: str, reset_at: datetime):
        self.key = key
        self.reset_at = reset_at
        super().__init__(f"Rate limit exceeded for '{key}'. Resets at '{reset_at}'")


class IntegrationTemplateException(IntegrationException):
    """Integration Template exception"""
    pass


class IntegrationFatalException(IntegrationException):
    """Integration Fatal exception"""
    pass


class IntegrationValidationException(IntegrationException):
    """Integration Validation exception"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(f"Validation error occurred, {self.message}")
#
#
# class IntegrationParamsException(IntegrationException):
#     """Integration Validation exception"""
#     pass

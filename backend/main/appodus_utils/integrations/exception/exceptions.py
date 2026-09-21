from datetime import datetime

from fastapi import status

from main.appodus_utils.exception.exceptions import AppodusBaseException


class IntegrationException(AppodusBaseException):
    """A failure while talking to an external provider.

    Carries ``status_code`` and ``code`` like every other ``AppodusBaseException``, because these
    do reach a request boundary — a provider failing during an OTP send, say. The global handler
    renders ``exc.status_code``/``exc.code``; without them it raised ``AttributeError`` inside the
    handler and the caller got an unmapped 500 instead of the error envelope.
    """

    def __init__(
        self,
        message: str,
        visible: bool = False,
        status_code: int = status.HTTP_502_BAD_GATEWAY,
        code: str = "INTEGRATION_ERROR",
    ):
        super().__init__(message, status_code=status_code, code=code)
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
        super().__init__(
            f"Rate limit exceeded for '{key}'. Resets at '{reset_at}'",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="INTEGRATION_RATE_LIMIT",
        )


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
        super().__init__(
            f"Validation error occurred, {self.message}",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INTEGRATION_VALIDATION_ERROR",
        )
#
#
# class IntegrationParamsException(IntegrationException):
#     """Integration Validation exception"""
#     pass

from typing import Optional, TypedDict, Any
from fastapi import status
from starlette.responses import Response


class ExceptionContext(TypedDict, total=False):
    """
    Structured metadata optionally attached to exceptions
    to provide context during logging, monitoring, or debugging.
    """
    user_id: str
    email: str
    fullname: str
    project_id: str
    order_id: str
    feature: str
    service: str
    limit_type: str
    endpoint: str
    payload: dict
    reason: str
    resource: str

class AppodusBaseException(Exception):
    """
    Base class for all Appodus exceptions.

    Attributes:
        message (str): Human-readable error message.
        status_code (int): HTTP status code to return in API response.
        code (str): Machine-readable error identifier.
        context (ExceptionContext): Optional dictionary providing structured metadata.
    """
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = "APPODUS_ERROR",
        context: Optional[ExceptionContext] = None
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        self.context = context or ExceptionContext()
        super().__init__(message)


# ────────────────────────────────
# Authentication & Authorization
# ────────────────────────────────

class UnauthorizedException(AppodusBaseException):
    def __init__(self, message: str = None):
        super().__init__(message or "Unauthorized access", status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED")


class ForbiddenException(AppodusBaseException):
    def __init__(self, message: str = None):
        super().__init__(message or "Forbidden action", status.HTTP_403_FORBIDDEN, "FORBIDDEN")


class InvalidTokenException(AppodusBaseException):
    def __init__(self, message: str = None):
        super().__init__(message or "Invalid or expired token", status.HTTP_401_UNAUTHORIZED, "INVALID_TOKEN")


class InvalidCredentialsException(AppodusBaseException):
    def __init__(self, message: str = None):
        super().__init__(message or "Invalid username or password", status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS")

class NoActiveSessionException(AppodusBaseException):
    def __init__(self, message: str = None):
        super().__init__(message or "No active session", status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED")


# ────────────────────────────────
# User Management
# ────────────────────────────────

class UserNotFoundException(AppodusBaseException):
    def __init__(self, user_id: str, message: str = None):
        super().__init__(
            message=message or f"User with ID {user_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
            code="USER_NOT_FOUND",
            context=ExceptionContext(user_id=user_id)
        )


class UserAlreadyExistsException(AppodusBaseException):
    def __init__(self, email: str, message: str = None):
        super().__init__(
            message=message or f"User with email {email} already exists",
            status_code=status.HTTP_409_CONFLICT,
            code="USER_ALREADY_EXISTS",
            context=ExceptionContext(email=email)
        )


# ────────────────────────────────
# Resource / CRUD Operations
# ────────────────────────────────

class ResourceNotFoundException(AppodusBaseException):
    def __init__(self, resource: str, message: str = None):
        super().__init__(
            message=message or f"{resource} not found",
            status_code=status.HTTP_404_NOT_FOUND,
            code="RESOURCE_NOT_FOUND",
            context=ExceptionContext(resource=resource)
        )


class ResourceConflictException(AppodusBaseException):
    def __init__(self, resource: str, message: str = None):
        super().__init__(
            message=message or f"Conflict while getting/creating/updating {resource}",
            status_code=status.HTTP_409_CONFLICT,
            code="RESOURCE_CONFLICT",
            context=ExceptionContext(resource=resource)
        )


class InvalidResourceStateException(AppodusBaseException):
    def __init__(self, resource: str, message: str = None):
        super().__init__(
            message=message or f"{resource} is in an invalid state",
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_RESOURCE_STATE",
            context=ExceptionContext(resource=resource)
        )


# ────────────────────────────────
# Validation
# ────────────────────────────────

class ValidationException(AppodusBaseException):
    def __init__(self, errors: list = None, message: str = None, context: Optional[ExceptionContext] = None):
        super().__init__(
            message=message or "Validation failed",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            context=context
        )
        self.details = errors

class TemplateRenderingException(AppodusBaseException):
    def __init__(self, message: str = None, context: Optional[ExceptionContext] = None):
        super().__init__(
            message=message or "Template rendering failed",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="TEMPLATE_RENDERING_ERROR",
            context=context
        )


# ────────────────────────────────
# System / Server Errors
# ────────────────────────────────

class InternalServerException(AppodusBaseException):
    def __init__(self, message: str = None):
        super().__init__(message or "Internal server error", status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR")


class DependencyException(AppodusBaseException):
    def __init__(self, service: str, message: str = None):
        super().__init__(
            message=message or f"Failed dependency: {service}",
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="DEPENDENCY_FAILURE",
            context=ExceptionContext(service=service)
        )


class NotImplementedException(AppodusBaseException):
    def __init__(self, message: str = None):
        super().__init__(message or "The requested feature is not implemented", status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR")

# ────────────────────────────────
# Integration / External APIs
# ────────────────────────────────

class ExternalAPIException(AppodusBaseException):
    def __init__(self, service: str, message: str = None):
        super().__init__(
            message=message or f"{service} API returned an error",
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="EXTERNAL_API_ERROR",
            context=ExceptionContext(service=service)
        )


class TimeoutException(AppodusBaseException):
    def __init__(self, service: str, message: str = None):
        super().__init__(
            message=message or f"Timeout while calling {service}",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            code="TIMEOUT_ERROR",
            context=ExceptionContext(service=service)
        )


class RateLimitException(AppodusBaseException):
    def __init__(self, service: str, message: str = None):
        super().__init__(
            message=message or f"Rate limited while calling {service}",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RATE_LIMIT_ERROR",
            context=ExceptionContext(service=service)
        )


class InsufficientBalanceException(AppodusBaseException):
    def __init__(self, service: str, message: str = None):
        super().__init__(
            message=message or f"Insufficient notice while calling {service}",
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            code="INSUFFICIENT_BALANCE_ERROR",
            context=ExceptionContext(service=service)
        )


# ────────────────────────────────
# Payments / Finance
# ────────────────────────────────

class PaymentFailedException(AppodusBaseException):
    def __init__(self, reason: str, message: str = None):
        super().__init__(
            message=message or f"Payment failed: {reason}",
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            code="PAYMENT_FAILED",
            context=ExceptionContext(reason=reason)
        )


class InvalidCardException(AppodusBaseException):
    def __init__(self, message: str = None):
        super().__init__(message or "Invalid card details", status.HTTP_400_BAD_REQUEST, "INVALID_CARD")


class SubscriptionRequiredException(AppodusBaseException):
    def __init__(self, message: str = None):
        super().__init__(message or "Subscription required to access this feature", status.HTTP_402_PAYMENT_REQUIRED, "SUBSCRIPTION_REQUIRED")


# ────────────────────────────────
# Business Logic / Domain-Specific
# ────────────────────────────────

class PlanLimitExceededException(AppodusBaseException):
    def __init__(self, limit_type: str, message: str = None):
        super().__init__(
            message=message or f"{limit_type} limit exceeded for current plan",
            status_code=status.HTTP_403_FORBIDDEN,
            code="PLAN_LIMIT_EXCEEDED",
            context=ExceptionContext(limit_type=limit_type)
        )


class FeatureNotAvailableException(AppodusBaseException):
    def __init__(self, feature: str, message: str = None):
        super().__init__(
            message=message or f"{feature} is not available in your current plan",
            status_code=status.HTTP_403_FORBIDDEN,
            code="FEATURE_NOT_AVAILABLE",
            context=ExceptionContext(feature=feature)
        )


class OrderNotCancelableException(AppodusBaseException):
    def __init__(self, order_id: str, message: str = None):
        super().__init__(
            message=message or f"Order {order_id} cannot be canceled",
            status_code=status.HTTP_400_BAD_REQUEST,
            code="ORDER_NOT_CANCELABLE",
            context=ExceptionContext(order_id=order_id)
        )


class SellerVerificationRequiredException(AppodusBaseException):
    def __init__(self, message: str = None):
        super().__init__(message or "Seller verification is required", status.HTTP_403_FORBIDDEN, "SELLER_NOT_VERIFIED")

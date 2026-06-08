"""Custom exceptions for the Gradescope transport layer."""


class GradescopeAPIError(Exception):
    """Base exception for Gradescope API errors."""


class AuthenticationError(GradescopeAPIError):
    """Raised when login fails or CSRF token extraction fails."""


class RateLimitError(GradescopeAPIError):
    """Raised when the Gradescope API returns a rate-limit response."""

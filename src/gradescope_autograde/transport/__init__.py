"""HTTP transport layer — session management and cookie persistence."""

from .exceptions import AuthenticationError, GradescopeAPIError, RateLimitError
from .session import GSSession

__all__ = ["AuthenticationError", "GSSession", "GradescopeAPIError", "RateLimitError"]

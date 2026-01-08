"""
Custom exceptions for the PyBirch API client.
"""


class APIError(Exception):
    """Base exception for API errors."""
    
    def __init__(self, message: str, code: str = None, status_code: int = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
    
    def __str__(self):
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


class AuthenticationError(APIError):
    """Raised when authentication fails or is required."""
    pass


class NotFoundError(APIError):
    """Raised when a resource is not found."""
    pass


class ValidationError(APIError):
    """Raised when request validation fails."""
    pass


class ConnectionError(APIError):
    """Raised when unable to connect to the API server."""
    pass


class RateLimitError(APIError):
    """Raised when rate limit is exceeded."""
    pass


class ServerError(APIError):
    """Raised when the server returns a 5xx error."""
    pass

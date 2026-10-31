"""Typed application errors translated at the HTTP boundary."""


class ApplicationError(Exception):
    """An expected operation failure with a stable public error contract."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class RateLimitExceeded(ApplicationError):
    """A request exceeded its configured authentication rate limit."""

    def __init__(self) -> None:
        super().__init__(429, "RATE_LIMITED", "Too many requests. Try again later.")


class RateLimitServiceUnavailable(ApplicationError):
    """Authentication cannot proceed when its required limiter is unavailable."""

    def __init__(self) -> None:
        super().__init__(
            503,
            "AUTH_SERVICE_UNAVAILABLE",
            "Authentication is temporarily unavailable.",
        )

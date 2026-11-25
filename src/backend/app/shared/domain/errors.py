"""Domain errors. The API layer maps them to HTTP codes (app/shared/api/errors.py)."""


class DomainError(Exception):
    """Business rule violated (-> 422)."""


class NotFound(DomainError):
    """Entity missing OR outside the caller's merchant scope (-> 404, never reveals existence)."""


class Forbidden(DomainError):
    """Authenticated but not allowed (-> 403)."""


class InvalidCredentials(DomainError):
    """Login failed. Message is deliberately generic (-> 401)."""

    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class InvalidStateTransition(DomainError):
    """Aggregate state machine refused a transition (-> 409)."""


class TooManyAttempts(DomainError):
    """Throttled (-> 429 with Retry-After)."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Too many failed login attempts. Try again later.")
        self.retry_after_seconds = retry_after_seconds

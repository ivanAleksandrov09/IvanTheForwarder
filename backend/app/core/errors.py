class NotFoundError(LookupError):
    """Mapped to HTTP 404."""


class ConflictError(RuntimeError):
    """Invalid state transition (e.g. sending an unapproved draft). Mapped to HTTP 409."""

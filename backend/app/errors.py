class DomainError(Exception):
    """Base class for errors the API reports to callers; each subclass carries its HTTP status."""

    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class BadRequestError(DomainError):
    status_code = 400


class ForbiddenError(DomainError):
    status_code = 403


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409


class ValidationFailedError(DomainError):
    status_code = 422

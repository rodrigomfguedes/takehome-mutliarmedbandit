from typing import Any


class AppException(Exception):
    """
    Base exception for expected application errors.
    """

    status_code: int = 400
    default_message: str = "An application error occurred."

    def __init__(
        self,
        message: str | None = None,
        details: Any | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details

        super().__init__(self.message)


class ExperimentNotFoundError(AppException):
    status_code = 404
    default_message = "Experiment not found."


class VariantNotFoundError(AppException):
    status_code = 404
    default_message = "Variant not found."


class InvalidObservationError(AppException):
    status_code = 400
    default_message = "The observation data is invalid."


class InvalidAllocationError(AppException):
    status_code = 400
    default_message = "The traffic allocation could not be calculated."


class DuplicateExperimentError(AppException):
    status_code = 409
    default_message = "An experiment with the same name already exists."


class DuplicateVariantError(AppException):
    status_code = 409
    default_message = (
        "A variant with the same name already exists in this experiment."
    )
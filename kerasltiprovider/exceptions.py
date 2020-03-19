import typing

from kerasltiprovider.types import AnyIDType


class KerasLTIProviderException(Exception):
    def __init__(
        self,
        message: str,
        user_id: typing.Optional[AnyIDType] = None,
        assignment_id: typing.Optional[AnyIDType] = None,
        status: int = 500,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.user_id = user_id
        self.assignment_id = assignment_id


class SubmissionValidationError(KerasLTIProviderException):
    pass


class InvalidGradingSubmissionException(KerasLTIProviderException):
    pass


class InvalidValidationHashTableException(KerasLTIProviderException):
    pass


class UnknownUserTokenException(KerasLTIProviderException):
    pass


class MissingAssignmentIDException(KerasLTIProviderException):
    pass


class SubmissionAfterDeadlineException(InvalidGradingSubmissionException):
    pass


class AssignmentException(KerasLTIProviderException):
    pass


class UnknownAssignmentException(AssignmentException):
    pass


class UnknownDatasetException(AssignmentException):
    pass


class MissingAssignmentsException(AssignmentException):
    pass


class PostingGradeFailedException(KerasLTIProviderException):
    pass


class ConfigurationErrorException(KerasLTIProviderException):
    pass


class NoDatabaseException(KerasLTIProviderException):
    pass

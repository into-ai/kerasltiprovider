import datetime
import logging
import os
import typing

from kerasltiprovider import context
from kerasltiprovider.database import Database
from kerasltiprovider.exceptions import (
    NoDatabaseException,
    SubmissionAfterDeadlineException,
    SubmissionValidationError,
    UnknownAssignmentException,
    UnknownDatasetException,
)
from kerasltiprovider.ingest import KerasAssignmentValidationSet
from kerasltiprovider.tracer import Tracer
from kerasltiprovider.types import AnyIDType, KerasBaseAssignment, PredType, ValHTType
from kerasltiprovider.utils import Datetime

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

logging.getLogger("tensorflow").setLevel(logging.ERROR)

log = logging.getLogger("kerasltiprovider")
log.addHandler(logging.NullHandler())


class KerasAssignment(KerasBaseAssignment):
    def __init__(
        self,
        name: str,
        identifier: AnyIDType,
        partial_loading: typing.Optional[bool] = False,
        submission_deadline: typing.Optional[datetime.datetime] = None,
        grading_callback: typing.Optional[typing.Callable[[float], float]] = None,
        validation_dataset: typing.Optional[KerasAssignmentValidationSet] = None,
    ):
        super().__init__(identifier=identifier)
        self.name = name
        self.submission_deadline = submission_deadline
        self.partial_loading = partial_loading
        self.grading_callback = grading_callback
        self.validation_dataset = validation_dataset

        # Will be lazily initialized
        self._validation_set_input_hashes: typing.Optional[typing.List[str]] = None
        self._validation_hash_table: typing.Optional[ValHTType] = None
        self._validation_set_size: typing.Optional[int] = None

    @property
    def formatted(self) -> typing.Dict[str, typing.Any]:
        return dict(
            name=self.name,
            identifier=self.identifier,
            submission_deadline="None"
            if not self.submission_deadline
            else self.submission_deadline.isoformat(),
        )

    def query_validation_set(self) -> None:
        if self.validation_dataset:
            self._validation_hash_table = self.validation_dataset.validation_hash_table

        # Lookup assignment data from database
        if not Database.assignments:
            raise NoDatabaseException(
                "Cannot load validation hash table without database"
            )

        self._validation_hash_table = dict()
        self._validation_set_size = 0
        self._validation_set_input_hashes = []
        for key in Database.assignments.scan_iter(match=f"{self.identifier}:*"):
            _predicted, _hash, _input = Database.assignments.hmget(
                key, "predicted", "hash", "input"
            )
            self._validation_set_size += 1
            self._validation_set_input_hashes.append(key)
            self._validation_hash_table[_hash] = dict(hash=_hash, predicted=_predicted)

    @property
    def validation_hash_table(self) -> ValHTType:
        if not self._validation_hash_table:
            self.query_validation_set()
        if self._validation_hash_table:
            return self._validation_hash_table
        raise ValueError("Failed to load validation hash table")

    @property
    def validation_set_size(self) -> int:
        if not self._validation_set_size:
            self.query_validation_set()
        if self._validation_set_size:
            return self._validation_set_size
        raise ValueError("Failed to calculate validation set size")

    @property
    def validation_set_input_hashes(self) -> typing.List[str]:
        if not self._validation_set_input_hashes:
            self.query_validation_set()
        if self._validation_set_input_hashes:
            return self._validation_set_input_hashes
        raise ValueError("Failed to calculate validation set input hashes")

    def still_open(self, date: typing.Optional[Datetime] = None) -> bool:
        with Tracer.main().start_active_span("KerasAssignment.still_open") as scope:
            if self.submission_deadline is None:
                return True
            scope.span.set_tag("date", date)
            date = date or Datetime.now()
            diff = (self.submission_deadline - date).total_seconds()
            scope.span.log_kv(dict(diff_seconds=diff, still_open=diff >= 0))
            return diff >= 0

    def validate(self, predictions: PredType) -> typing.Tuple[float, float]:
        with Tracer.main().start_active_span("KerasAssignment.validate") as scope:
            scope.span.set_tag("predictions", predictions)
            if not self.still_open():
                raise SubmissionAfterDeadlineException(
                    f"The deadline for submission was on {'?' if not self.submission_deadline else self.submission_deadline.isoformat()}"
                )
            if not len(predictions) == self.validation_set_size:
                raise SubmissionValidationError(
                    f"Expected {self.validation_set_size} predictions"
                )
            num_correct = 0
            if not Database.assignments:
                raise NoDatabaseException
            for matrix_hash, prediction in predictions.items():
                reference_prediction = self.validation_hash_table.get(
                    matrix_hash, dict()
                ).get("predicted")
                if reference_prediction is None:
                    raise UnknownDatasetException(
                        "Cannot validate your results. Is this the correct assignment?"
                    )
                elif prediction is None:
                    pass
                else:
                    if float(reference_prediction) == float(prediction):
                        num_correct += 1

            accuracy = round(num_correct / self.validation_set_size, ndigits=2)
            score = round(
                accuracy
                if not self.grading_callback
                else self.grading_callback(accuracy),
                ndigits=2,
            )
            scope.span.log_kv(
                dict(num_correct=num_correct, score=score, accuracy=accuracy)
            )
            return accuracy, score


def find_assignment(assignment_id: AnyIDType) -> KerasAssignment:
    try:
        return [
            a for a in context.assignments if str(a.identifier) == str(assignment_id)
        ][0]
    except (TypeError, ValueError, IndexError):
        raise UnknownAssignmentException(
            f'Could not find assignment with id "{assignment_id}"'
        )

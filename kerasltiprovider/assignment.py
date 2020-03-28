import datetime
import json
import logging
import os
import typing
from typing import TYPE_CHECKING

import cachetools
import numpy as np

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

if TYPE_CHECKING:  # pragma: no cover
    from kerasltiprovider.selection import SelectionStrategy  # noqa: F401
    from kerasltiprovider.processing import PostprocessingStep  # noqa: F401

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

    @property
    def formatted(self) -> typing.Dict[str, typing.Any]:
        return dict(
            name=self.name,
            identifier=self.identifier,
            submission_deadline="None"
            if not self.submission_deadline
            else self.submission_deadline.isoformat(),
        )

    # Cache for 16 hours
    @cachetools.cached(cachetools.TTLCache(1, 16 * 60 * 60))
    def validation_hash_table(self) -> ValHTType:
        if self.validation_dataset:
            return self.validation_dataset.validation_hash_table()

        # Lookup assignment data from database
        if not Database.assignments:
            raise NoDatabaseException(
                "Cannot load validation hash table without database"
            )

        validation_hash_table: ValHTType = dict()
        for key in Database.assignments.scan_iter(match=f"{self.identifier}:*"):
            _predicted, _hash, _input = Database.assignments.hmget(
                key, "predicted", "hash", "input"
            )
            validation_hash_table[_hash] = dict(
                matrix=np.asarray(json.loads(_input)), predicted=_predicted
            )
        return validation_hash_table

    # Cache for 16 hours
    @cachetools.cached(cachetools.TTLCache(1, 16 * 60 * 60))
    def validation_set_size(self) -> int:
        if self.validation_dataset:
            return self.validation_dataset.validation_set_size

        # Lookup assignment data from database
        if not Database.assignments:
            raise NoDatabaseException(
                "Cannot calculate validation_set_size without database"
            )

        size = 0
        for _ in Database.assignments.scan_iter(match=f"{self.identifier}:*"):
            size += 1
        return size

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
            if not len(predictions) == self.validation_set_size():
                raise SubmissionValidationError(
                    f"Expected {self.validation_set_size()} predictions"
                )
            num_correct = 0
            if not Database.assignments:
                raise NoDatabaseException
            for matrix_hash, prediction in predictions.items():
                reference_prediction = Database.assignments.hget(
                    self.input_key_for(matrix_hash), "predicted"
                )
                if reference_prediction is None:
                    raise UnknownDatasetException(
                        "Cannot validate your results. Is this the correct assignment?"
                    )
                elif prediction is None:
                    pass
                else:
                    if float(reference_prediction) == float(prediction):
                        num_correct += 1

            accuracy = round(num_correct / self.validation_set_size(), ndigits=2)
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
